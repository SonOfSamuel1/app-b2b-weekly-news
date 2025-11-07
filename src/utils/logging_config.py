"""Structured logging configuration for the weekly news automation."""
import logging
import json
import sys
from typing import Any, Dict


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs JSON-structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add any extra fields
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Set up structured logging for the application.

    Args:
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    # Get root logger
    logger = logging.getLogger('weekly_news')
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers = []

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Use structured formatter for production, simple for local
    if sys.stdout.isatty():
        # Local development - use simple format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        # Production - use JSON format
        formatter = StructuredFormatter()

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(f'weekly_news.{name}')


def log_with_context(logger: logging.Logger, level: int, message: str, **kwargs) -> None:
    """Log a message with additional context fields.

    Args:
        logger: Logger instance
        level: Log level (logging.INFO, logging.ERROR, etc.)
        message: Log message
        **kwargs: Additional context fields
    """
    extra = {'extra_fields': kwargs}
    logger.log(level, message, extra=extra)
