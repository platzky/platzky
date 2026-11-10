from typing import Any

import pytest

from platzky.db.exceptions import InvalidDataError
from platzky.db.json_document import JsonDocument, JsonSection
from platzky.db.json_plugin_config_repository import JsonPluginConfigRepository
from platzky.db.json_stores import MemoryStore


def _repository(data: dict[str, Any]) -> JsonPluginConfigRepository:
    return JsonPluginConfigRepository(JsonSection(JsonDocument(MemoryStore(data)), "plugins"))


class TestJsonPluginConfigRepository:
    def test_get_all_returns_validated_configs(self):
        data = {"plugins": {"my_plugin": {"is_active": True, "config": {"key": "value"}}}}
        repository = _repository(data)

        plugins = repository.get_all()

        assert plugins["my_plugin"].is_active is True
        assert plugins["my_plugin"].config == {"key": "value"}

    def test_get_all_returns_empty_dict_when_missing(self):
        repository = _repository({})
        assert repository.get_all() == {}

    def test_get_all_raises_when_plugins_is_none(self):
        repository = _repository({"plugins": None})
        with pytest.raises(InvalidDataError, match="plugins"):
            repository.get_all()
