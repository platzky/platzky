from unittest.mock import Mock

import pytest

from platzky.db.exceptions import InvalidDataError
from platzky.db.json_document import JsonDocument, JsonSection
from platzky.db.json_stores import JsonStore, MemoryStore


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

    def test_edit_yields_the_same_dict_and_saves_on_success(self):
        store = Mock(spec=JsonStore)
        data = {"site_config": {}}
        store.load.return_value = data
        document = JsonDocument(store)

        with document.edit() as edited:
            assert edited is data
            edited["x"] = 1

        assert document.data is data
        store.save.assert_called_once_with({"site_config": {}, "x": 1})

    def test_edit_saves_when_block_returns_early(self):
        store = Mock(spec=JsonStore)
        store.load.return_value = {"a": 1}
        document = JsonDocument(store)

        def edit_and_return() -> str:
            with document.edit() as edited:
                edited["a"] = 2
                return "early"

        assert edit_and_return() == "early"
        store.save.assert_called_once_with({"a": 2})
        with document.edit():
            pass
        assert store.save.call_count == 2

    def test_edit_releases_lock_and_restores_when_save_raises_base_exception(self):
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

        assert data == {"a": 1}
        edit_and_save()
        assert data == {"a": 2}

    def test_edit_does_not_save_on_exception_and_releases_lock(self):
        store = Mock(spec=JsonStore)
        store.load.return_value = {"a": 1}
        document = JsonDocument(store)

        def edit_and_fail() -> None:
            with document.edit() as edited:
                edited["a"] = 2
                raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            edit_and_fail()

        store.save.assert_not_called()
        assert document.data == {"a": 1}
        with document.edit():
            pass
        store.save.assert_called_once()

    def test_edit_restores_in_place_when_save_fails(self):
        store = Mock(spec=JsonStore)
        data = {"a": {"b": 1}}
        store.load.return_value = data
        store.save.side_effect = OSError("disk")
        document = JsonDocument(store)

        def edit_and_save() -> None:
            with document.edit() as edited:
                edited["a"]["b"] = 2
                edited["added"] = True

        with pytest.raises(OSError, match="disk"):
            edit_and_save()

        assert document.data is data
        assert data == {"a": {"b": 1}}


class TestJsonSection:
    def test_data_is_the_section_only(self):
        section = JsonSection(JsonDocument(MemoryStore({"a": {"x": 1}, "b": {"y": 2}})), "a")

        assert dict(section.data) == {"x": 1}

    def test_data_is_read_only(self):
        section = JsonSection(JsonDocument(MemoryStore({"a": {"x": 1}})), "a")

        with pytest.raises(TypeError):
            section.data["x"] = 2  # type: ignore[index]

    def test_missing_section_is_empty(self):
        assert dict(JsonSection(JsonDocument(MemoryStore({})), "a").data) == {}

    @pytest.mark.parametrize("value", [None, [], "text", 5])
    def test_section_that_is_not_an_object_is_an_error(self, value: object):
        section = JsonSection(JsonDocument(MemoryStore({"a": value})), "a")

        with pytest.raises(InvalidDataError, match=r"^a: "):
            section.data

    def test_edit_yields_the_section_and_saves_the_document(self):
        store = Mock(spec=JsonStore)
        store.load.return_value = {"a": {"x": 1}, "b": 2}
        section = JsonSection(JsonDocument(store), "a")

        with section.edit() as edited:
            edited["x"] = 5

        store.save.assert_called_once_with({"a": {"x": 5}, "b": 2})

    def test_edit_creates_a_missing_section(self):
        store = Mock(spec=JsonStore)
        store.load.return_value = {}

        with JsonSection(JsonDocument(store), "a").edit() as edited:
            edited["x"] = 5

        store.save.assert_called_once_with({"a": {"x": 5}})

    def test_edit_restores_the_document_when_the_block_raises(self):
        document = JsonDocument(MemoryStore({"a": {"x": 1}}))
        section = JsonSection(document, "a")

        with pytest.raises(RuntimeError), section.edit() as edited:
            edited["x"] = 5
            raise RuntimeError

        assert document.data == {"a": {"x": 1}}

    def test_edit_of_a_section_that_is_not_an_object_is_an_error_and_releases_the_lock(self):
        document = JsonDocument(MemoryStore({"a": None}))
        section = JsonSection(document, "a")

        with pytest.raises(InvalidDataError), section.edit():
            pass
        with pytest.raises(InvalidDataError), section.edit():
            pass
