"""Unified logging configuration."""
import logging
import logging.config
import sys
import uuid
from contextvars import ContextVar

from fastapi import Request

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id_var.get()


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger with request-id-aware format."""
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": RequestIdFilter},
        },
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "default",
                "filters": ["request_id"],
            },
        },
        "loggers": {
            "": {"handlers": ["console"], "level": level},
            "uvicorn": {"handlers": ["console"], "level": level, "propagate": False},
            "uvicorn.error": {"handlers": ["console"], "level": level, "propagate": False},
            "uvicorn.access": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        },
    })


async def request_id_middleware(request: Request, call_next):
    """Attach X-Request-ID to every request and bind it to the contextvar."""
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    token = _request_id_var.set(rid)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        _request_id_var.reset(token)
