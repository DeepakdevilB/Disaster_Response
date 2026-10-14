"""Structured logging.

Every log record is emitted as a single JSON object per line (``LOG_FORMAT=json``), which is
what log shippers (Loki, ELK, CloudWatch…) expect. The current request id is attached
automatically from a context variable set by :class:`app.core.middleware.RequestContextMiddleware`.

Usage::

    logger = logging.getLogger(__name__)
    logger.info("report queued", extra={"report_id": str(report.id)})
"""

from __future__ import annotations

import json
import logging
import logging.config
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes present on every LogRecord; anything else came from `extra=` and is emitted as-is.
_STANDARD_ATTRS = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys()
    | {"message", "asctime", "taskName"}
)


class JsonFormatter(logging.Formatter):
    """Render a LogRecord as one line of JSON."""

    def __init__(self, service: str = "api") -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service,
        }
        request_id = request_id_ctx.get()
        if request_id:
            payload["request_id"] = request_id

        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Human-friendly single-line format for local debugging (``LOG_FORMAT=console``)."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-8s %(name)s [%(request_id)s] %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_ctx.get() or "-"
        return super().format(record)


def configure_logging(level: str = "INFO", fmt: str = "json", service: str = "api") -> None:
    """Configure the root logger and route uvicorn's loggers through it.

    Uvicorn's own access log is disabled because the request middleware emits a richer,
    structured access log line (with request id and duration).
    """
    formatter: dict[str, Any] = (
        {"()": JsonFormatter, "service": service} if fmt == "json" else {"()": ConsoleFormatter}
    )
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"default": formatter},
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "default",
                }
            },
            "root": {"level": level, "handlers": ["stdout"]},
            "loggers": {
                "uvicorn": {"level": level, "handlers": [], "propagate": True},
                "uvicorn.error": {"level": level, "handlers": [], "propagate": True},
                "uvicorn.access": {"level": "WARNING", "handlers": [], "propagate": False},
                # Keep chatty libraries quiet unless debugging.
                "sqlalchemy.engine": {"level": "WARNING"},
                "amqp": {"level": "WARNING"},
                "httpx": {"level": "WARNING"},
                "httpcore": {"level": "WARNING"},
            },
        }
    )
