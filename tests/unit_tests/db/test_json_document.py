from unittest.mock import Mock

import pytest

from platzky.db.exceptions import InvalidDataError, ReadOnlyStorageError
from platzky.db.json_document import JsonDocument, JsonSection
from platzky.db.json_stores import JsonStore, MemoryStore, ReadOnlyStore


class TestJsonDocument:
    def test_loads_the_store_once_and_keeps_it(self):
        store = Mock(spec=JsonStore)
        store.load.return_value = {"site_config": {}}

        document = JsonDocument(store)

        store.load.assert_called_once_with()
        assert document.data == {"site_config": {}}

    def test_data_is_the_loaded_dict(self):
        data = {"site_config": {}}
        assert JsonDocument(MemoryStore(data)).data is data

    def test_edit_saves_a_copy_and_then_makes_it_the_document(self):
        store = MemoryStore({"site_config": {}})
        document = JsonDocument(store)

        with document.edit() as edited:
            edited["x"] = 1
            assert document.data == {"site_config": {}}

        assert (store.load(), document.data) == (
            {"site_config": {}, "x": 1},
            {"site_config": {}, "x": 1},
        )

    def test_edit_saves_when_block_returns_early(self):
        store = MemoryStore({"a": 1})
        document = JsonDocument(store)

        def edit_and_return() -> str:
            with document.edit() as edited:
                edited["a"] = 2
                return "early"

        assert edit_and_return() == "early"
        assert store.load() == {"a": 2}
        with document.edit() as edited:
            edited["a"] = 3
        assert store.load() == {"a": 3}

    def test_edit_releases_lock_and_keeps_the_document_when_save_raises_base_exception(self):
        store = Mock(spec=JsonStore)
        data = {"a": 1}
        store.load.return_value = data
        store.save.side_effect = [KeyboardInterrupt, None]
        document = JsonDocument(store)

        def edit_and_save() -> None:
            with document.edit() as edited:
                edited["a"] = 2

        with pytest.raises(KeyboardInterrupt):
            edit_and_save()

        assert document.data == {"a": 1}
        edit_and_save()
        assert document.data == {"a": 2}

    def test_edit_does_not_save_on_exception_and_releases_lock(self):
        store = MemoryStore({"a": 1})
        document = JsonDocument(store)

        def edit_and_fail() -> None:
            with document.edit() as edited:
                edited["a"] = 2
                raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            edit_and_fail()

        assert (store.load(), document.data) == ({"a": 1}, {"a": 1})
        with document.edit() as edited:
            edited["a"] = 3
        assert store.load() == {"a": 3}

    def test_edit_keeps_the_document_when_save_fails(self):
        data = {"a": {"b": 1}}
        document = JsonDocument(ReadOnlyStore(data))

        def edit_and_save() -> None:
            with document.edit() as edited:
                edited["a"]["b"] = 2
                edited["added"] = True

        with pytest.raises(ReadOnlyStorageError):
            edit_and_save()

        assert document.data is data
        assert data == {"a": {"b": 1}}


class TestJsonSection:
    def test_section_is_a_read_only_mapping_of_its_content_only(self):
        section = JsonSection(JsonDocument(MemoryStore({"a": {"x": 1}, "b": {"y": 2}})), "a")

        assert dict(section) == {"x": 1}
        with pytest.raises(TypeError):
            section["x"] = 2  # type: ignore[index]

    def test_section_shows_a_write_made_through_the_document(self):
        document = JsonDocument(MemoryStore({"a": {"x": 1}}))
        section = JsonSection(document, "a")

        with document.edit() as data:
            data["a"]["x"] = 2

        assert dict(section) == {"x": 2}

    def test_missing_section_is_empty(self):
        assert dict(JsonSection(JsonDocument(MemoryStore({})), "a")) == {}

    @pytest.mark.parametrize("value", [None, [], "text", 5])
    def test_section_that_is_not_an_object_is_an_error(self, value: object):
        with pytest.raises(InvalidDataError, match=r"^a: "):
            JsonSection(JsonDocument(MemoryStore({"a": value})), "a")

    def test_edit_saves_the_document_and_then_shows_the_change(self):
        store = MemoryStore({"a": {"x": 1}, "b": 2})
        section = JsonSection(JsonDocument(store), "a")

        with section.edit() as edited:
            edited["x"] = 5

        assert (store.load(), dict(section)) == ({"a": {"x": 5}, "b": 2}, {"x": 5})

    def test_edit_creates_a_missing_section(self):
        store = MemoryStore({})

        with JsonSection(JsonDocument(store), "a").edit() as edited:
            edited["x"] = 5

        assert store.load() == {"a": {"x": 5}}

    def test_edit_that_raises_changes_nothing(self):
        document = JsonDocument(MemoryStore({"a": {"x": 1}}))
        section = JsonSection(document, "a")

        with pytest.raises(RuntimeError), section.edit() as edited:
            edited["x"] = 5
            raise RuntimeError

        assert (document.data, dict(section)) == ({"a": {"x": 1}}, {"x": 1})

    def test_edit_whose_save_fails_changes_nothing(self):
        section = JsonSection(JsonDocument(ReadOnlyStore({"a": {"x": 1}})), "a")

        with pytest.raises(ReadOnlyStorageError), section.edit() as edited:
            edited["x"] = 5

        assert dict(section) == {"x": 1}

    def test_readers_never_see_an_edit_in_progress(self):
        section = JsonSection(JsonDocument(MemoryStore({"a": {"x": 1}})), "a")

        with section.edit() as edited:
            edited["x"] = 5
            assert dict(section) == {"x": 1}
