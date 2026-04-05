"""MongoDB query filter sanitizer to prevent NoSQL injection.

Standalone copy of the API-side sanitizer for use in MCP tool handlers.
MCP is a separate package and cannot import from hydra-api.
"""

from typing import Any

# Safe MongoDB query operators that are allowed in user-provided filters.
ALLOWED_OPERATORS: frozenset[str] = frozenset(
    {
        # Comparison
        "$eq",
        "$ne",
        "$gt",
        "$gte",
        "$lt",
        "$lte",
        "$in",
        "$nin",
        # Logical
        "$and",
        "$or",
        "$not",
        "$nor",
        # Element
        "$exists",
        "$type",
        # Evaluation (safe subset)
        "$regex",
        "$options",
        # Array
        "$elemMatch",
        "$size",
        "$all",
    }
)

MAX_FILTER_DEPTH = 10


class BlockedOperatorError(ValueError):
    """Raised when a blocked MongoDB operator is detected in a filter."""


def sanitize_mongo_filter(
    filter_dict: dict[str, Any],
    *,
    _depth: int = 0,
) -> dict[str, Any]:
    """Recursively validate a MongoDB filter dict against the operator allowlist.

    Args:
        filter_dict: The filter dictionary to validate.

    Returns:
        The validated filter dictionary (unchanged if valid).

    Raises:
        BlockedOperatorError: If a blocked operator is found or depth limit exceeded.
    """
    if _depth > MAX_FILTER_DEPTH:
        raise BlockedOperatorError("Filter exceeds maximum nesting depth")

    if not isinstance(filter_dict, dict):
        return filter_dict

    for key, value in filter_dict.items():
        if isinstance(key, str) and key.startswith("$") and key not in ALLOWED_OPERATORS:
            raise BlockedOperatorError(f"Blocked MongoDB operator: {key}")

        # Recurse into nested dicts
        if isinstance(value, dict):
            sanitize_mongo_filter(value, _depth=_depth + 1)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    sanitize_mongo_filter(item, _depth=_depth + 1)

    return filter_dict
