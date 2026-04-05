"""Shared JSON Schema hardening helpers for MCP tool inputs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

ID_LIKE_FIELD_NAMES = {
    "actorId",
    "commandId",
    "entityId",
    "groupId",
    "networkId",
    "nodeId",
    "resourceId",
    "serviceId",
}
ENUM_LIKE_FIELD_NAMES = {
    "action",
    "category",
    "class",
    "collection",
    "groupBy",
    "mode",
    "runtime",
    "service",
    "source",
    "status",
    "type",
}
FREE_TEXT_FIELD_NAMES = {"query", "resourceType", "scope"}
TIMESTAMP_FIELD_NAMES = {"since", "timestamp", "until"}
VERSION_FIELD_NAMES = {"fromVersion", "toVersion", "version"}

IDENTIFIER_MAX_LENGTH = 128
ENUM_MAX_LENGTH = 64
FREE_TEXT_MAX_LENGTH = 256
TIMESTAMP_MAX_LENGTH = 64
VERSION_MAX_LENGTH = 64
DEFAULT_STRING_MAX_LENGTH = IDENTIFIER_MAX_LENGTH
DEFAULT_ARRAY_MAX_ITEMS = 25
DEFAULT_OBJECT_MAX_PROPERTIES = 20
PROJECTION_MAX_PROPERTIES = 25
LIST_LIMIT_MAX = 200
AUDIT_LIMIT_MAX = 500
DEPENDENCY_DEPTH_MAX = 10


def harden_tool_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Apply shared hardening rules to an MCP tool input schema."""
    hardened = deepcopy(schema)
    if hardened.get("type") != "object":
        return hardened

    properties = hardened.setdefault("properties", {})
    hardened.setdefault("additionalProperties", False)
    hardened.setdefault("maxProperties", len(properties))

    for name, prop in properties.items():
        if isinstance(prop, dict):
            _harden_property(name, prop)

    return hardened


def _harden_property(name: str, prop: dict[str, Any]) -> None:
    prop_type = prop.get("type")

    if prop_type == "string":
        prop.setdefault("maxLength", _infer_string_max_length(name, prop))
        return

    if prop_type == "array":
        prop.setdefault("maxItems", _infer_array_max_items(name, prop))
        _harden_array_items(name, prop.get("items"))
        return

    if prop_type == "object":
        prop.setdefault("maxProperties", _infer_object_max_properties(name))
        if name == "projection":
            prop.setdefault(
                "additionalProperties",
                {"type": "integer", "enum": [0, 1]},
            )
        return

    if prop_type == "integer":
        _harden_integer_property(name, prop)


def _harden_array_items(name: str, items: Any) -> None:
    if not isinstance(items, dict):
        return
    if items.get("type") != "string" or "maxLength" in items:
        return

    if isinstance(items.get("enum"), list) or name in {"tags", "sections"}:
        items["maxLength"] = ENUM_MAX_LENGTH
    else:
        items["maxLength"] = DEFAULT_STRING_MAX_LENGTH


def _harden_integer_property(name: str, prop: dict[str, Any]) -> None:
    if name == "limit":
        prop.setdefault("minimum", 1)
        prop.setdefault(
            "maximum",
            AUDIT_LIMIT_MAX if prop.get("default") == 100 else LIST_LIMIT_MAX,
        )
        return

    if name in {"offset", "skip"}:
        prop.setdefault("minimum", 0)
        return

    if name == "depth":
        prop.setdefault("minimum", 1)
        prop.setdefault("maximum", DEPENDENCY_DEPTH_MAX)


def _infer_string_max_length(name: str, prop: dict[str, Any]) -> int:
    if name in TIMESTAMP_FIELD_NAMES:
        return TIMESTAMP_MAX_LENGTH

    if name in VERSION_FIELD_NAMES:
        return VERSION_MAX_LENGTH

    if name in ID_LIKE_FIELD_NAMES or name.endswith("Id"):
        return IDENTIFIER_MAX_LENGTH

    if name in FREE_TEXT_FIELD_NAMES:
        return FREE_TEXT_MAX_LENGTH

    if name in ENUM_LIKE_FIELD_NAMES or isinstance(prop.get("enum"), list):
        return ENUM_MAX_LENGTH

    return DEFAULT_STRING_MAX_LENGTH


def _infer_array_max_items(name: str, prop: dict[str, Any]) -> int:
    if name == "tags":
        return 25
    if name == "sections":
        return 5

    items = prop.get("items")
    if isinstance(items, dict) and isinstance(items.get("enum"), list):
        return len(items["enum"])

    return DEFAULT_ARRAY_MAX_ITEMS


def _infer_object_max_properties(name: str) -> int:
    if name == "projection":
        return PROJECTION_MAX_PROPERTIES
    return DEFAULT_OBJECT_MAX_PROPERTIES
