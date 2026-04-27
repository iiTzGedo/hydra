"""Entity-context template variable resolution for embedded panels."""

from __future__ import annotations

import re
from typing import Any

_PATTERN = re.compile(r"\{\{\s*entity\.(id|type)\s*\}\}")


def _substitute(value: str, entity_type: str, entity_id: str) -> str:
    return _PATTERN.sub(
        lambda m: entity_id if m.group(1) == "id" else entity_type, value
    )


def resolve_entity_vars(binding: dict[str, Any], entity_type: str, entity_id: str) -> dict[str, Any]:
    """Substitute {{entity.id}} and {{entity.type}} in a single binding dict."""
    return {
        k: _substitute(v, entity_type, entity_id) if isinstance(v, str) else v
        for k, v in binding.items()
    }


def resolve_entity_vars_deep(obj: Any, entity_type: str, entity_id: str) -> Any:
    """Recursively substitute in any str leaves of dict/list structures."""
    if isinstance(obj, str):
        return _substitute(obj, entity_type, entity_id)
    if isinstance(obj, dict):
        return {k: resolve_entity_vars_deep(v, entity_type, entity_id) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_entity_vars_deep(v, entity_type, entity_id) for v in obj]
    return obj
