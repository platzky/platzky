import json
from pathlib import Path

import pytest

from platzky.db.json_db import Json
from platzky.db.json_file_db import JsonFile
from platzky.db.json_stores import MemoryStore

DATA = {"site_content": {"pages": []}}


def test_document_exposes_the_data_the_database_reads():
    db = Json(MemoryStore({"site_content": {"pages": [], "app_name": "Marker"}}))

    assert db.document.data["site_content"]["app_name"] == "Marker"


def test_document_edit_is_visible_to_the_database():
    db = Json(MemoryStore({"site_content": {"pages": []}}))

    with db.document.edit() as data:
        data["site_content"]["pages"].append(
            {"title": "t", "slug": "added", "contentInMarkdown": "c", "author": "a", "excerpt": "e"}
        )

    assert [page.slug for page in db.blog.pages.get_all("en")] == ["added"]


def test_document_edit_is_persisted_by_file_store(tmp_path: Path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps(DATA))
    db = JsonFile(str(path))

    with db.document.edit() as data:
        data["custom"] = {"key": "value"}

    assert json.loads(path.read_text())["custom"] == {"key": "value"}


def test_document_cannot_be_replaced():
    db = Json(MemoryStore(DATA))

    with pytest.raises(AttributeError):
        setattr(db, "document", None)
