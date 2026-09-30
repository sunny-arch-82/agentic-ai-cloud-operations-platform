"""JSON logs on stderr: stdout is reserved for MCP messages or CLI JSON."""

import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record):
        result = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        result.update(getattr(record, "fields", {}))
        return json.dumps(result, default=str)


def configure(level="INFO"):
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)


def event(name: str, **fields):
    logging.getLogger("opspilot").info(name, extra={"fields": fields})
