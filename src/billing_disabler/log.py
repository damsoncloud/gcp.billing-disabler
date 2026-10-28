"""Structured logging understood by Cloud Logging."""

import json
import logging
import sys
from enum import StrEnum
from typing import Any, override


class LogEvent(StrEnum):
    """Values of the `event` log field, intended as stable filters for log-based alerts."""

    BILLING_DISABLED = "billing_disabled"
    BILLING_DISABLING_FAILED = "billing_disabling_failed"
    BILLING_DISABLING_SIMULATED = "billing_disabling_simulated"
    NOTIFICATION_DISCARDED = "notification_discarded"


class CloudLoggingFormatter(logging.Formatter):
    """Formats records as single-line JSON, which Cloud Run forwards to Cloud Logging as `jsonPayload`.

    Additional payload fields are passed with `extra={"fields": {...}}`.
    """

    @override
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            **getattr(record, "fields", {}),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Route all log records to stdout as Cloud Logging structured entries.

    Args:
        level: Minimum severity of emitted records.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CloudLoggingFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
