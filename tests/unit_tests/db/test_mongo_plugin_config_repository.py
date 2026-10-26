from typing import cast
from unittest.mock import Mock

from platzky.db.mongo_plugin_config_repository import MongoPluginConfigRepository


class TestMongoPluginConfigRepository:
    def test_get_all_returns_validated_configs(self):
        plugins = Mock()
        cast(Mock, plugins.find_one).return_value = {
            "_id": "config",
            "data": {"my_plugin": {"is_active": True, "config": {"key": "value"}}},
        }
        repository = MongoPluginConfigRepository(plugins)

        result = repository.get_all()

        assert result["my_plugin"].is_active is True
        assert result["my_plugin"].config == {"key": "value"}

    def test_get_all_returns_empty_dict_when_no_document(self):
        plugins = Mock()
        cast(Mock, plugins.find_one).return_value = None
        repository = MongoPluginConfigRepository(plugins)

        assert repository.get_all() == {}

    def test_get_all_returns_empty_dict_when_data_key_missing(self):
        plugins = Mock()
        cast(Mock, plugins.find_one).return_value = {"_id": "config"}
        repository = MongoPluginConfigRepository(plugins)

        assert repository.get_all() == {}
