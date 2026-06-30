import json
import logging
import sys
from datetime import UTC, datetime


class ServiceNameFilter(logging.Filter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def filter(self, record):
        if not hasattr(record, "service"):
            record.service = self.service_name
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", "unknown-service"),
            "logger": record.name,
            "message": record.getMessage(),
        }

        extra_fields = [
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "client",
            "user_id",
            "order_id",
            "item_id",
            "error_type",
        ]

        for field in extra_fields:
            value = getattr(record, field, None)
            if value is not None:
                log_record[field] = value

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


def setup_logging(service_name: str):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ServiceNameFilter(service_name))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
