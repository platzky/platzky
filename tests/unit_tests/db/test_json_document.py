from unittest.mock import Mock

import pytest

from platzky.db.exceptions import DBError
from platzky.db.json_document import JsonDocument, get_site_content
from platzky.db.json_stores import JsonStore, MemoryStore


class TestJsonDocument:
    def test_loads_the_store_once_and_keeps_it(self):
        store = Mock(spec=JsonStore)
        store.load.return_value = {"site_content": {}}

        document = JsonDocument(store)

        store.load.assert_called_once_with()
        assert document.data == {"site_content": {}}

    def test_data_is_the_loaded_dict(self):
        data = {"site_content": {}}
        assert JsonDocument(MemoryStore(data)).data is data

    def test_edit_yields_the_same_dict_and_saves_on_success(self):
        store = Mock(spec=JsonStore)
        data = {"site_content": {}}
        store.load.return_value = data
        document = JsonDocument(store)

        with document.edit() as edited:
            assert edited is data
            edited["x"] = 1

        assert document.data is data
        store.save.assert_called_once_with({"site_content": {}, "x": 1})

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

        with pytest.raises(RuntimeError):
            with document.edit() as edited:
                edited["a"] = 2
                raise RuntimeError("boom")

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

        with pytest.raises(OSError):
            with document.edit() as edited:
                edited["a"]["b"] = 2
                edited["added"] = True

        assert document.data is data
        assert data == {"a": {"b": 1}}


class TestGetSiteContent:
    def test_returns_site_content(self):
        assert get_site_content({"site_content": {"a": 1}}) == {"a": 1}

    @pytest.mark.parametrize("data", [{}, {"site_content": None}, {"site_content": []}])
    def test_raises_when_missing_or_not_a_dict(self, data: dict[str, object]):
        with pytest.raises(DBError):
            get_site_content(data)
