"""
AEGIS Structured JSON Logger (Backend/app/logging_setup.py)
Formats all log output as JSON and automatically redacts sensitive headers, tokens, and credentials (PRD Part 2c s7).
"""

import hashlib
import json
import logging
import sys
import time
from typing import Any

SENSITIVE_KEYS = {
    "authorization",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "cookie",
    "set-cookie",
    "api_key",
    "manifest",
}


def redact_sensitive_data(data: Any) -> Any:
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_sensitive_data(v)
        return redacted
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data


def hash_user_id(user_id: str | None) -> str | None:
    if not user_id:
        return None
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include custom context attributes if present
        for attr in ("request_id", "method", "path", "status_code", "duration_ms", "user_hash"):
            val = getattr(record, attr, None)
            if val is not None:
                log_payload[attr] = val

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(redact_sensitive_data(log_payload))


def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("aegis")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = setup_logging()
