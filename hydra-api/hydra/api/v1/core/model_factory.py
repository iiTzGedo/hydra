"""Resilient Pydantic materialization helpers for MongoDB rows.

Background
----------

The API stores documents in MongoDB which has no schema enforcement, then
re-validates them through Pydantic models on the way out. When the model
layer evolves (enum values change, fields become required, etc.) older
rows can fail validation and take the entire response down with a 500.

For **list endpoints** that's a UX disaster — one stale row wipes out the
whole UI. For **detail endpoints** (single document GET) it's the right
behavior — silently returning ``None`` for the resource the caller
asked for would be more confusing than the 500.

This module provides two helpers:

- :func:`safe_materialize_many` — skip + log invalid rows; return what we
  can.
- :func:`safe_materialize_one` — re-raise as :class:`MaterializationError`
  with structured context for the caller's exception handler.
"""

from __future__ import annotations

from typing import Any, TypeVar

import structlog
from pydantic import BaseModel, ValidationError

logger = structlog.get_logger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)


class MaterializationError(RuntimeError):
    """Raised by :func:`safe_materialize_one` when a row fails validation.

    Carries the originating ``ValidationError`` plus the document's
    primary identifier (when supplied) so the caller can decide how to
    surface the failure (404, 500, etc.).
    """

    def __init__(
        self,
        model_name: str,
        identifier: str | None,
        validation_error: ValidationError,
    ) -> None:
        message = (
            f"Failed to materialize {model_name}"
            + (f"({identifier})" if identifier else "")
            + f": {validation_error}"
        )
        super().__init__(message)
        self.model_name = model_name
        self.identifier = identifier
        self.validation_error = validation_error


def safe_materialize_many(
    model: type[ModelT],
    rows: list[dict[str, Any]],
    *,
    context: str,
    id_field: str = "_id",
) -> list[ModelT]:
    """Convert a list of MongoDB rows into Pydantic instances, skipping bad ones.

    Args:
        model: The Pydantic response/summary model class.
        rows: Raw rows fetched from MongoDB.
        context: Short label for logs (e.g. ``"nodes_list"``); shows up
            in the structured warning when a row is dropped so operators
            can find the offending collection.
        id_field: Name of the field that uniquely identifies the row.
            Used for log correlation. Defaults to ``"_id"``.

    Returns:
        List of valid Pydantic instances. Invalid rows are skipped and
        logged at WARN with their identifier and the validation error.
    """
    valid: list[ModelT] = []
    skipped = 0

    for row in rows:
        try:
            valid.append(model(**row))
        except ValidationError as exc:
            skipped += 1
            row_id = row.get(id_field) if isinstance(row, dict) else None
            logger.warning(
                "model_factory.row_skipped",
                context=context,
                model=model.__name__,
                row_id=row_id,
                error=str(exc),
            )

    if skipped:
        logger.warning(
            "model_factory.partial_response",
            context=context,
            model=model.__name__,
            returned=len(valid),
            skipped=skipped,
            total=len(rows),
        )

    return valid


def safe_materialize_one(
    model: type[ModelT],
    row: dict[str, Any],
    *,
    context: str,
    identifier: str | None = None,
) -> ModelT:
    """Convert a single MongoDB row into a Pydantic instance.

    Unlike :func:`safe_materialize_many`, this re-raises validation
    errors as :class:`MaterializationError` so the caller can decide
    whether to surface a 500 or translate to a 404. Detail endpoints
    should *not* silently drop the requested resource.

    Args:
        model: Pydantic model class.
        row: Raw row from MongoDB.
        context: Log label for correlation.
        identifier: Optional identifier (typically the URL path param)
            used in the log + raised exception.

    Raises:
        MaterializationError: The row exists but cannot be validated.
    """
    try:
        return model(**row)
    except ValidationError as exc:
        logger.error(
            "model_factory.materialization_failed",
            context=context,
            model=model.__name__,
            identifier=identifier,
            error=str(exc),
        )
        raise MaterializationError(model.__name__, identifier, exc) from exc
