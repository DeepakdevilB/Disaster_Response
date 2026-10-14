"""ASGI middleware: request id propagation and structured access logging."""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_ctx

REQUEST_ID_HEADER = "X-Request-ID"
# Accept caller-supplied ids only if they are short and safe, to prevent log injection.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")

access_logger = logging.getLogger("app.access")


class RequestContextMiddleware:
    """Assigns a request id, echoes it in the response, and logs one line per request.

    Implemented as pure ASGI middleware (not ``BaseHTTPMiddleware``) so it does not buffer
    streaming responses and keeps the context variable visible to the endpoint.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = _header(scope, REQUEST_ID_HEADER.lower())
        request_id = (
            incoming if incoming and _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        )
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()
        status_code = 500  # if the app crashes before sending headers

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            access_logger.info(
                "%s %s %s",
                scope["method"],
                scope["path"],
                status_code,
                extra={
                    "http_method": scope["method"],
                    "http_path": scope["path"],
                    "http_status": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": scope["client"][0] if scope.get("client") else None,
                },
            )
            request_id_ctx.reset(token)


def _header(scope: Scope, name: str) -> str | None:
    target = name.encode("latin-1")
    for key, value in scope.get("headers", []):
        if key == target:
            return value.decode("latin-1")
    return None
