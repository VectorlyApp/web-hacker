"""
tests/unit/test_data_utils.py

Unit tests for data utility functions.
"""

import pytest

from bluebox.utils.data_utils import extract_object_schema


class TestExtractObjectSchema:
    """Test cases for extract_object_schema function."""

    def test_scalar_string(self) -> None:
        """Scalar string returns scalar type."""
        result = extract_object_schema("hello")
        assert result == {"_type": "scalar", "_count": 1}

    def test_scalar_int(self) -> None:
        """Scalar integer returns scalar type."""
        result = extract_object_schema(42)
        assert result == {"_type": "scalar", "_count": 1}

    def test_scalar_float(self) -> None:
        """Scalar float returns scalar type."""
        result = extract_object_schema(3.14)
        assert result == {"_type": "scalar", "_count": 1}

    def test_scalar_bool(self) -> None:
        """Scalar boolean returns scalar type."""
        result = extract_object_schema(True)
        assert result == {"_type": "scalar", "_count": 1}

    def test_scalar_none(self) -> None:
        """Scalar None returns scalar type."""
        result = extract_object_schema(None)
        assert result == {"_type": "scalar", "_count": 1}

    def test_empty_dict(self) -> None:
        """Empty dict returns dict type with no fields."""
        result = extract_object_schema({})
        assert result == {"_type": "dict"}

    def test_simple_dict(self) -> None:
        """Simple dict returns dict type with field schemas."""
        result = extract_object_schema({"name": "Alice", "age": 30})
        assert result["_type"] == "dict"
        assert result["name"] == {"_type": "scalar", "_count": 1}
        assert result["age"] == {"_type": "scalar", "_count": 1}

    def test_nested_dict(self) -> None:
        """Nested dict returns nested schema structure."""
        data = {"user": {"name": "Alice", "email": "alice@example.com"}}
        result = extract_object_schema(data)
        assert result["_type"] == "dict"
        assert result["user"]["_type"] == "dict"
        assert result["user"]["name"] == {"_type": "scalar", "_count": 1}
        assert result["user"]["email"] == {"_type": "scalar", "_count": 1}

    def test_empty_list(self) -> None:
        """Empty list returns list type with empty items."""
        result = extract_object_schema([])
        assert result == {"_type": "list", "_count": 0, "_items": {}}

    def test_list_of_scalars(self) -> None:
        """List of scalars returns list with scalar items."""
        result = extract_object_schema([1, 2, 3])
        assert result["_type"] == "list"
        assert result["_count"] == 3
        assert result["_items"] == {"_type": "scalar"}

    def test_list_of_strings(self) -> None:
        """List of strings returns list with scalar items."""
        result = extract_object_schema(["a", "b", "c"])
        assert result["_type"] == "list"
        assert result["_count"] == 3
        assert result["_items"] == {"_type": "scalar"}

    def test_list_of_dicts_same_keys(self) -> None:
        """List of dicts with same keys merges schemas."""
        data = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
        result = extract_object_schema(data)
        assert result["_type"] == "list"
        assert result["_count"] == 2
        assert result["_items"]["_type"] == "dict"
        assert "id" in result["_items"]
        assert "name" in result["_items"]

    def test_list_of_dicts_different_keys(self) -> None:
        """List of dicts with different keys includes all keys."""
        data = [{"id": 1, "name": "a"}, {"id": 2, "email": "b@example.com"}]
        result = extract_object_schema(data)
        assert result["_type"] == "list"
        assert result["_count"] == 2
        assert result["_items"]["_type"] == "dict"
        assert "id" in result["_items"]
        assert "name" in result["_items"]
        assert "email" in result["_items"]

    def test_list_of_dicts_partial_keys(self) -> None:
        """List of dicts where some items have fewer keys."""
        data = [{"id": 1, "name": "a"}, {"id": 2}]
        result = extract_object_schema(data)
        assert result["_type"] == "list"
        assert result["_count"] == 2
        assert result["_items"]["_type"] == "dict"
        assert "id" in result["_items"]
        assert "name" in result["_items"]

    def test_deeply_nested_structure(self) -> None:
        """Deeply nested structure preserves all levels."""
        data = {
            "level1": {
                "level2": {
                    "level3": {"value": 42}
                }
            }
        }
        result = extract_object_schema(data)
        assert result["_type"] == "dict"
        assert result["level1"]["_type"] == "dict"
        assert result["level1"]["level2"]["_type"] == "dict"
        assert result["level1"]["level2"]["level3"]["_type"] == "dict"
        assert result["level1"]["level2"]["level3"]["value"] == {"_type": "scalar", "_count": 1}

    def test_dict_with_list_field(self) -> None:
        """Dict containing a list field."""
        data = {"items": [1, 2, 3], "count": 3}
        result = extract_object_schema(data)
        assert result["_type"] == "dict"
        assert result["items"]["_type"] == "list"
        assert result["items"]["_count"] == 3
        assert result["count"] == {"_type": "scalar", "_count": 1}

    def test_list_of_dicts_with_nested_lists(self) -> None:
        """List of dicts where dicts contain lists."""
        data = [
            {"id": 1, "tags": ["a", "b"]},
            {"id": 2, "tags": ["c"]},
        ]
        result = extract_object_schema(data)
        assert result["_type"] == "list"
        assert result["_count"] == 2
        assert result["_items"]["_type"] == "dict"
        assert "id" in result["_items"]
        assert "tags" in result["_items"]

    def test_list_of_nested_dicts(self) -> None:
        """List of dicts with nested dict fields."""
        data = [
            {"user": {"name": "Alice"}},
            {"user": {"name": "Bob", "age": 30}},
        ]
        result = extract_object_schema(data)
        assert result["_type"] == "list"
        assert result["_count"] == 2
        assert result["_items"]["_type"] == "dict"
        assert result["_items"]["user"]["_type"] == "dict"
        assert "name" in result["_items"]["user"]
        assert "age" in result["_items"]["user"]

    def test_complex_api_response_structure(self) -> None:
        """Complex structure mimicking typical API response."""
        data = {
            "status": "success",
            "data": {
                "users": [
                    {"id": 1, "name": "Alice", "roles": ["admin", "user"]},
                    {"id": 2, "name": "Bob", "roles": ["user"]},
                ],
                "total": 2,
            },
            "meta": {"version": "1.0"},
        }
        result = extract_object_schema(data)

        assert result["_type"] == "dict"
        assert result["status"] == {"_type": "scalar", "_count": 1}
        assert result["data"]["_type"] == "dict"
        assert result["data"]["users"]["_type"] == "list"
        assert result["data"]["users"]["_count"] == 2
        assert result["data"]["users"]["_items"]["_type"] == "dict"
        assert "id" in result["data"]["users"]["_items"]
        assert "name" in result["data"]["users"]["_items"]
        assert "roles" in result["data"]["users"]["_items"]
        assert result["data"]["total"] == {"_type": "scalar", "_count": 1}
        assert result["meta"]["_type"] == "dict"
        assert result["meta"]["version"] == {"_type": "scalar", "_count": 1}

    def test_list_of_lists(self) -> None:
        """List containing lists (matrix-like structure)."""
        data = [[1, 2], [3, 4], [5, 6]]
        result = extract_object_schema(data)
        assert result["_type"] == "list"
        assert result["_count"] == 3

    def test_mixed_list_non_dict_items(self) -> None:
        """List with mixed non-dict items returns scalar items."""
        data = [1, "two", 3.0, True]
        result = extract_object_schema(data)
        assert result["_type"] == "list"
        assert result["_count"] == 4
        assert result["_items"] == {"_type": "scalar"}
