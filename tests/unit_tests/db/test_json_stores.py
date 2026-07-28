import json
import os
from pathlib import Path

import pytest

from platzky.db.exceptions import ReadOnlyStorageError
from platzky.db.json_stores import FileStore, MemoryStore, ReadOnlyStore


class TestMemoryStore:
    def test_load_returns_same_instance(self):
        data = {"a": 1}
        store = MemoryStore(data)
        assert store.load() is data

    def test_save_succeeds_and_updates_reference(self):
        store = MemoryStore({"a": 1})
        new_data = {"a": 2}
        store.save(new_data)
        assert store.load() is new_data


class TestReadOnlyStore:
    def test_load_returns_wrapped_data(self):
        data = {"a": 1}
        store = ReadOnlyStore(data)
        assert store.load() is data

    def test_save_raises_read_only_storage_error(self):
        store = ReadOnlyStore({"a": 1})
        with pytest.raises(ReadOnlyStorageError):
            store.save({"a": 2})


class TestFileStore:
    def test_load_reads_json_file(self, tmp_path: Path):
        path = tmp_path / "data.json"
        path.write_text(json.dumps({"a": 1}))
        store = FileStore(str(path))
        assert store.load() == {"a": 1}

    def test_save_round_trips(self, tmp_path: Path):
        path = tmp_path / "data.json"
        path.write_text(json.dumps({"a": 1}))
        store = FileStore(str(path))
        store.save({"a": 2, "b": [1, 2, 3]})
        assert store.load() == {"a": 2, "b": [1, 2, 3]}

    def test_save_is_atomic_no_partial_file_left_behind(self, tmp_path: Path):
        path = tmp_path / "data.json"
        path.write_text(json.dumps({"a": 1}))
        store = FileStore(str(path))

        store.save({"a": 2})

        # Only the target file should exist in the directory; no leaked temp file.
        assert os.listdir(tmp_path) == ["data.json"]

    def test_save_leaves_original_file_intact_if_serialization_fails(self, tmp_path: Path):
        path = tmp_path / "data.json"
        original = {"a": 1}
        path.write_text(json.dumps(original))
        store = FileStore(str(path))

        class Unserializable:
            pass

        unserializable_data = {"a": Unserializable()}

        with pytest.raises(TypeError):
            store.save(unserializable_data)

        # Original file is untouched, and no leaked temp file remains.
        assert json.loads(path.read_text()) == original
        assert os.listdir(tmp_path) == ["data.json"]

    def test_save_creates_new_file_if_missing(self, tmp_path: Path):
        path = tmp_path / "new.json"
        store = FileStore(str(path))
        store.save({"a": 1})
        assert json.loads(path.read_text()) == {"a": 1}
