from typing import Any

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
