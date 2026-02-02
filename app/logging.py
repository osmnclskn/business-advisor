import json
import logging
import sys
from functools import lru_cache
from typing import Any

from app.config import get_settings
from app.utils import utc_now


def _extract_extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    extras = {}
    if hasattr(record, "session_id"):
        extras["session_id"] = record.session_id
    if hasattr(record, "agent"):
        extras["agent"] = record.agent
    if hasattr(record, "duration_ms"):
        extras["duration_ms"] = record.duration_ms

    return extras


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": utc_now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **_extract_extra_fields(record),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class SimpleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = utc_now().strftime("%H:%M:%S")
        extras = _extract_extra_fields(record)

        extra_parts = []
        if "session_id" in extras:
            extra_parts.append(f"session={extras['session_id']}")
        if "agent" in extras:
            extra_parts.append(f"agent={extras['agent']}")
        if "duration_ms" in extras:
            extra_parts.append(f"duration={extras['duration_ms']}ms")

        extra_str = f" [{', '.join(extra_parts)}]" if extra_parts else ""

        return f"{timestamp} | {record.levelname:<8} | {record.name}{extra_str} | {record.getMessage()}"


@lru_cache(maxsize=1)
def setup_logging() -> logging.Logger:
    settings = get_settings()

    logger = logging.getLogger("advisor")
    logger.setLevel(getattr(logging, settings.log_level.upper()))

    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)

    if settings.app_env == "production":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(SimpleFormatter())

    logger.addHandler(handler)
    logger.propagate = False

    return logger


def get_logger() -> logging.Logger:
    return setup_logging()


class LogContext:
    def __init__(self, **kwargs):
        self.extras = kwargs
        self._old_factory = None

    def __enter__(self):
        self._old_factory = logging.getLogRecordFactory()
        extras = self.extras
        old_factory = self._old_factory

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            for key, value in extras.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self._old_factory)
