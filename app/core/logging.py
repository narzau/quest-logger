import logging
import sys
import os
from typing import Dict, Any, Optional
import json
from datetime import datetime
import contextlib
import contextvars
from pathlib import Path

from app.core.config import settings

# Global context variable for request information
request_context = contextvars.ContextVar("request_context", default={})


class JsonFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings after parsing the log record.
    """

    def __init__(self, **kwargs):
        self.fmt_dict = kwargs

    def format(self, record: logging.LogRecord) -> str:
        record_dict = self._prepare_log_dict(record)
        return json.dumps(record_dict)

    def _prepare_log_dict(self, record: logging.LogRecord) -> Dict[str, Any]:
        record_dict = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include exception info if available
        if record.exc_info:
            record_dict["exception"] = self.formatException(record.exc_info)

        # Include custom fields from the record
        for key, value in self.fmt_dict.items():
            if key in record.__dict__:
                record_dict[key] = record.__dict__[key]

        # Include extra attributes passed via extra parameter
        if hasattr(record, "extras"):
            for key, value in record.extras.items():
                record_dict[key] = value

        # Include request context information if available
        context = request_context.get()
        if context:
            for key, value in context.items():
                # Don't overwrite existing keys
                if key not in record_dict:
                    record_dict[key] = value

        return record_dict


class ContextFilter(logging.Filter):
    """
    Filter that adds request context data to log records.
    """

    def filter(self, record):
        # Add the current request context to the record
        context = request_context.get()
        if context:
            for key, value in context.items():
                setattr(record, key, value)
        return True


def setup_logging(level: Optional[str] = None):
    """
    Set up logging for the application.

    Args:
        level: Optional log level override (default to settings)
    """
    log_level = getattr(logging, level or settings.LOG_LEVEL)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add context filter to all loggers
    context_filter = ContextFilter()
    root_logger.addFilter(context_filter)

    # Create console handler for development
    console_handler = logging.StreamHandler(sys.stdout)

    # Use JSON formatter in production
    if settings.ENVIRONMENT == "production":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s (%(filename)s:%(lineno)d) - %(message)s"
        )

    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # Add file handler if LOG_FILE is set
    if settings.LOG_FILE:
        try:
            # Ensure log directory exists
            log_path = Path(settings.LOG_FILE)
            log_dir = log_path.parent
            os.makedirs(log_dir, exist_ok=True)

            # Create file handler
            file_handler = logging.FileHandler(settings.LOG_FILE)
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            root_logger.addHandler(file_handler)
        except Exception as e:
            print(f"Error setting up file logging: {e}")

    # Set specific levels for third-party loggers to reduce noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Return the logger for convenience
    return logging.getLogger("app")


@contextlib.contextmanager
def log_context(**context_data):
    """
    Context manager for adding context to logs.

    Usage:
        with log_context(user_id=123, action="login"):
            logger.info("User logged in")

    Args:
        **context_data: Key-value pairs to add to log context
    """
    # Get current context
    current_context = request_context.get().copy()

    # Update with new context data
    current_context.update(context_data)

    # Set the new context
    token = request_context.set(current_context)

    try:
        yield
    finally:
        # Restore previous context
        request_context.reset(token)


# Create a default app logger
logger = setup_logging()
