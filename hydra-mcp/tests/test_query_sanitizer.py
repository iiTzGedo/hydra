"""Tests for MongoDB query filter sanitizer."""

import pytest

from hydra_mcp.query_sanitizer import (
    ALLOWED_OPERATORS,
    MAX_FILTER_DEPTH,
    BlockedOperatorError,
    sanitize_mongo_filter,
)


class TestAllowedOperators:
    """Verify the operator allowlist is complete and correct."""

    def test_comparison_operators_allowed(self) -> None:
        for op in ("$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$in", "$nin"):
            assert op in ALLOWED_OPERATORS

    def test_logical_operators_allowed(self) -> None:
        for op in ("$and", "$or", "$not", "$nor"):
            assert op in ALLOWED_OPERATORS

    def test_element_operators_allowed(self) -> None:
        for op in ("$exists", "$type"):
            assert op in ALLOWED_OPERATORS

    def test_evaluation_operators_allowed(self) -> None:
        for op in ("$regex", "$options"):
            assert op in ALLOWED_OPERATORS

    def test_array_operators_allowed(self) -> None:
        for op in ("$elemMatch", "$size", "$all"):
            assert op in ALLOWED_OPERATORS

    def test_dangerous_operators_not_allowed(self) -> None:
        dangerous = ("$where", "$function", "$accumulator", "$expr", "$jsonSchema")
        for op in dangerous:
            assert op not in ALLOWED_OPERATORS


class TestSanitizeMongoFilter:
    """Test sanitize_mongo_filter validation logic."""

    def test_simple_field_equality(self) -> None:
        f = {"status": "active", "name": "nginx"}
        result = sanitize_mongo_filter(f)
        assert result == f

    def test_allowed_comparison_operator(self) -> None:
        f = {"count": {"$gte": 5, "$lte": 100}}
        result = sanitize_mongo_filter(f)
        assert result == f

    def test_allowed_logical_operator(self) -> None:
        f = {"$and": [{"status": "active"}, {"class": "compute"}]}
        result = sanitize_mongo_filter(f)
        assert result == f

    def test_allowed_in_operator(self) -> None:
        f = {"status": {"$in": ["active", "inactive"]}}
        result = sanitize_mongo_filter(f)
        assert result == f

    def test_allowed_regex_operator(self) -> None:
        f = {"name": {"$regex": "^nginx", "$options": "i"}}
        result = sanitize_mongo_filter(f)
        assert result == f

    def test_allowed_exists_operator(self) -> None:
        f = {"parentNodeId": {"$exists": True}}
        result = sanitize_mongo_filter(f)
        assert result == f

    def test_allowed_elemMatch_operator(self) -> None:
        f = {"tags": {"$elemMatch": {"$eq": "production"}}}
        result = sanitize_mongo_filter(f)
        assert result == f

    def test_blocked_where_operator(self) -> None:
        with pytest.raises(BlockedOperatorError, match=r"Blocked MongoDB operator: \$where"):
            sanitize_mongo_filter({"$where": "this.status == 'active'"})

    def test_blocked_function_operator(self) -> None:
        with pytest.raises(BlockedOperatorError, match=r"Blocked MongoDB operator: \$function"):
            sanitize_mongo_filter({"value": {"$function": {"body": "return true"}}})

    def test_blocked_accumulator_operator(self) -> None:
        with pytest.raises(BlockedOperatorError, match=r"Blocked MongoDB operator: \$accumulator"):
            sanitize_mongo_filter({"$accumulator": {}})

    def test_blocked_operator_in_nested_dict(self) -> None:
        f = {"field": {"nested": {"$where": "1==1"}}}
        with pytest.raises(BlockedOperatorError, match=r"\$where"):
            sanitize_mongo_filter(f)

    def test_blocked_operator_in_list_item(self) -> None:
        f = {"$and": [{"$where": "1==1"}]}
        with pytest.raises(BlockedOperatorError, match=r"\$where"):
            sanitize_mongo_filter(f)

    def test_deeply_nested_allowed(self) -> None:
        """Filters within depth limit should pass."""
        f: dict[str, object] = {"level0": {"level1": {"level2": {"$eq": 1}}}}
        result = sanitize_mongo_filter(f)
        assert result == f

    def test_exceeds_max_depth(self) -> None:
        """Filters deeper than MAX_FILTER_DEPTH are rejected."""
        # Build a dict nested deeper than the limit
        inner: dict[str, object] = {"value": 1}
        for i in range(MAX_FILTER_DEPTH + 2):
            inner = {f"level{i}": inner}
        with pytest.raises(BlockedOperatorError, match="maximum nesting depth"):
            sanitize_mongo_filter(inner)

    def test_non_dict_input_returns_unchanged(self) -> None:
        """Non-dict values pass through without error."""
        result = sanitize_mongo_filter("not a dict")  # type: ignore[arg-type]
        assert result == "not a dict"

    def test_empty_filter(self) -> None:
        result = sanitize_mongo_filter({})
        assert result == {}

    def test_mixed_operators_and_fields(self) -> None:
        f = {
            "status": "active",
            "$or": [
                {"class": "compute"},
                {"tags": {"$in": ["production"]}},
            ],
            "count": {"$gt": 0},
        }
        result = sanitize_mongo_filter(f)
        assert result == f

    def test_non_string_keys_ignored(self) -> None:
        """Non-string keys (unusual but possible) should not trigger blocking."""
        f = {123: "value"}  # type: ignore[dict-item]
        result = sanitize_mongo_filter(f)
        assert result == f

    def test_list_with_non_dict_items(self) -> None:
        """Lists containing primitives should not cause errors."""
        f = {"tags": {"$all": ["web", "production", 42]}}
        result = sanitize_mongo_filter(f)
        assert result == f


class TestBlockedOperatorError:
    """Test the custom exception class."""

    def test_is_value_error(self) -> None:
        assert issubclass(BlockedOperatorError, ValueError)

    def test_message_preserved(self) -> None:
        err = BlockedOperatorError("test message")
        assert str(err) == "test message"
