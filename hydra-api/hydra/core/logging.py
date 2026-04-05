"""Structured logging configuration."""

import logging
import sys
from typing import Any

import structlog

from hydra.core.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure structured logging for the application.

    Args:
        settings: Application settings containing log level and format.
    """
    renderer: structlog.types.Processor
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)


def get_request_logger(request_id: str, **kwargs: Any) -> structlog.BoundLogger:
    """Get a logger bound with request context.

    Args:
        request_id: Unique request identifier.
        **kwargs: Additional context to bind to the logger.

    Returns:
        BoundLogger instance with request context.
    """
    return structlog.get_logger().bind(request_id=request_id, **kwargs)  # type: ignore[no-any-return]
