from platzky.db.json_plugin_config_repository import JsonPluginConfigRepository


class TestJsonPluginConfigRepository:
    def test_get_all_returns_validated_configs(self):
        data = {"plugins": {"my_plugin": {"is_active": True, "config": {"key": "value"}}}}
        repository = JsonPluginConfigRepository(data)

        plugins = repository.get_all()

        assert plugins["my_plugin"].is_active is True
        assert plugins["my_plugin"].config == {"key": "value"}

    def test_get_all_returns_empty_dict_when_missing(self):
        repository = JsonPluginConfigRepository({})
        assert repository.get_all() == {}

    def test_get_all_returns_empty_dict_when_plugins_is_none(self):
        repository = JsonPluginConfigRepository({"plugins": None})
        assert repository.get_all() == {}
