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
        assert document.store is store

    def test_data_is_the_loaded_dict(self):
        data = {"site_content": {}}
        assert JsonDocument(MemoryStore(data)).data is data


class TestGetSiteContent:
    def test_returns_site_content(self):
        assert get_site_content({"site_content": {"a": 1}}) == {"a": 1}

    @pytest.mark.parametrize("data", [{}, {"site_content": None}, {"site_content": []}])
    def test_raises_when_missing_or_not_a_dict(self, data: dict[str, object]):
        with pytest.raises(DBError):
            get_site_content(data)
