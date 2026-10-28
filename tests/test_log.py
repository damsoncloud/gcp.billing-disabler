"""Tests of structured logging."""

import json
import logging
import sys

import pytest

from billing_disabler.log import CloudLoggingFormatter, configure_logging


def make_record(**kwargs: object) -> logging.LogRecord:
    """Create a log record with the given extra attributes."""
    record = logging.LogRecord("test", logging.WARNING, __file__, 1, "Hello %s", ("world",), None)
    record.__dict__.update(kwargs)
    return record


def test_format_emits_cloud_logging_entry() -> None:
    """Record is formatted as JSON with severity, message and extra fields."""
    entry = json.loads(CloudLoggingFormatter().format(make_record(fields={"event": "billing_disabled"})))

    assert entry == {"severity": "WARNING", "message": "Hello world", "logger": "test", "event": "billing_disabled"}


def test_format_includes_exception() -> None:
    """Exception traceback is included."""
    try:
        raise ValueError("boom")
    except ValueError:
        record = make_record(exc_info=sys.exc_info())

    entry = json.loads(CloudLoggingFormatter().format(record))

    assert "ValueError: boom" in entry["exception"]


def test_configure_logging_writes_json_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """Configured root logger writes formatted entries to stdout."""
    configure_logging()

    logging.getLogger("test").info("Hello")

    assert json.loads(capsys.readouterr().out)["message"] == "Hello"
