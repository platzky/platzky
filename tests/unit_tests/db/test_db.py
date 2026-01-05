from collections.abc import Callable
from typing import Any, cast

import pytest

from platzky.db.db import DB
from platzky.db.json_db import Json


def dummy_function_taking_one_argument(_: Any):
    return "test"


def test_db_extension():
    db = Json(
        {
            "DB": {
                "TYPE": "json",
                "DATA": {
                    "site_content": {
                        "pages": [
                            {
                                "title": "test",
                                "slug": "test",
                                "contentInMarkdown": "test",
                            },
                            {
                                "title": "test2",
                                "slug": "test2",
                                "contentInMarkdown": "test2",
                            },
                        ]
                    }
                },
            }
        }
    )

    # TODO remove ignores with proper plugin system
    with pytest.raises(AttributeError):
        db.test()  # type: ignore

    db.extend("test", dummy_function_taking_one_argument)
    result = db.test()  # type: ignore
    assert result == "test"


def test_db_doesnt_allow_its_children_to_add_new_methods():
    with pytest.raises(TypeError):

        class TestDB(DB):
            def test(self):
                return "test"


def test_db_extend_error_cases():
    db = Json(
        {
            "DB": {
                "TYPE": "json",
                "DATA": {"site_content": {"pages": []}},
            }
        }
    )

    non_callable = cast(Callable[..., Any], object())

    with pytest.raises(ValueError, match="not callable"):
        db.extend("test_non_callable", non_callable)


def test_db_extend_with_existing_name():
    db = Json(
        {
            "DB": {
                "TYPE": "json",
                "DATA": {"site_content": {"pages": []}},
            }
        }
    )

    # First extension works fine
    db.extend("test_function", dummy_function_taking_one_argument)

    # For the test to fail, we need to mock setattr to make it raise an exception
    # when attempting to set an existing attribute
    original_setattr = setattr

    def mocked_setattr(*args, **kwargs):
        # Simulate an exception when setting an existing attribute
        if args[1] == "test_function" or args[1] == "extend":
            raise AttributeError("Cannot set attribute - already exists")
        return original_setattr(*args, **kwargs)

    # Apply the mock
    import builtins

    original = builtins.setattr
    builtins.setattr = mocked_setattr

    try:
        # Now these should raise ValueError from the try/except in extend
        with pytest.raises(ValueError, match="Failed to extend DB"):
            db.extend("test_function", dummy_function_taking_one_argument)

        with pytest.raises(ValueError, match="Failed to extend DB"):
            db.extend("extend", dummy_function_taking_one_argument)
    finally:
        # Restore original setattr
        builtins.setattr = original
