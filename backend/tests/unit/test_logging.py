"""Structured JSON logging and the per-request access log."""

from __future__ import annotations

import json
import logging

from app.core.logging import JsonFormatter, configure_logging, request_id_ctx


def _record(msg: str = "hello %s", args: tuple = ("world",), **extra) -> logging.LogRecord:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, msg, args, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_emits_one_valid_json_object():
    line = JsonFormatter(service="api").format(_record())

    assert "\n" not in line
    payload = json.loads(line)
    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["service"] == "api"
    assert payload["timestamp"].endswith("+00:00")
    assert "request_id" not in payload


def test_json_formatter_includes_request_id_from_context():
    token = request_id_ctx.set("req-123")
    try:
        payload = json.loads(JsonFormatter().format(_record()))
    finally:
        request_id_ctx.reset(token)
    assert payload["request_id"] == "req-123"


def test_json_formatter_includes_extra_fields_and_serialises_unknown_types():
    class Custom:
        def __str__(self) -> str:
            return "custom!"

    payload = json.loads(JsonFormatter().format(_record(report_id="r1", obj=Custom())))
    assert payload["report_id"] == "r1"
    assert payload["obj"] == "custom!"


def test_json_formatter_includes_exception_traceback():
    try:
        raise ValueError("bad value")
    except ValueError:
        import sys

        record = logging.LogRecord(
            "app.test", logging.ERROR, __file__, 1, "failed", (), sys.exc_info()
        )
    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError: bad value" in payload["exc_info"]


def test_configure_logging_writes_json_to_stdout(capsys):
    configure_logging(level="INFO", fmt="json", service="unit")
    logging.getLogger("app.something").info("structured", extra={"k": 1})

    line = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload == {**payload, "message": "structured", "k": 1, "service": "unit"}


def test_access_log_line_per_request(make_client, caplog):
    client = make_client()  # create_app() reconfigures logging, dropping pytest's root handler
    access_logger = logging.getLogger("app.access")
    access_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.INFO, logger="app.access"):
            response = client.get("/health", headers={"X-Request-ID": "trace-1"})
    finally:
        access_logger.removeHandler(caplog.handler)

    records = [r for r in caplog.records if r.name == "app.access"]
    assert len(records) == 1
    record = records[0]
    assert record.http_method == "GET"
    assert record.http_path == "/health"
    assert record.http_status == response.status_code == 200
    assert record.duration_ms >= 0
    # The request id is in the context while the access line is formatted.
    assert response.headers["X-Request-ID"] == "trace-1"
