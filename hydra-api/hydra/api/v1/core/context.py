"""Request-scoped context variables for async-safe propagation."""

from contextvars import ContextVar

_request_id_var: ContextVar[str] = ContextVar("request_id", default="unknown")


def get_request_id() -> str:
    """Get the current request ID from context."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set the request ID in the current async context."""
    _request_id_var.set(request_id)
