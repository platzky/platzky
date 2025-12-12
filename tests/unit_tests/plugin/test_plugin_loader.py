from unittest import mock

import pytest

from platzky.config import Config
from platzky.platzky import create_app_from_config
from platzky.plugin.plugin import ConfigPluginError, PluginBase, PluginBaseConfig, PluginError
from tests.unit_tests.plugin import fake_plugin


@pytest.fixture
def base_config_data():
    """Base configuration for tests."""
    return {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "test_secret",
        "USE_WWW": False,
        "BLOG_PREFIX": "/",
        "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
        "DB": {
            "TYPE": "json",
            "DATA": {"plugins": []},
        },
    }


@pytest.fixture
def mock_plugin_setup():
    """Setup mocks for plugin loading."""
    with (
        mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find_plugin,
        mock.patch("platzky.plugin.plugin_loader._get_plugin_class") as mock_get_plugin_class,
    ):
        yield mock_find_plugin, mock_get_plugin_class


class TestPluginErrors:
    def test_invalid_plugin_config(self, base_config_data):
        base_config_data["DB"]["DATA"]["plugins"] = [{"name": "redirections", "config": None}]
        config = Config.model_validate(base_config_data)

        with pytest.raises(PluginError):
            create_app_from_config(config)

    def test_non_existent_plugin(self, base_config_data):
        base_config_data["DB"]["DATA"]["plugins"] = [{"name": "non_existent_plugin", "config": {}}]
        config = Config.model_validate(base_config_data)

        with pytest.raises(PluginError):
            create_app_from_config(config)

    def test_plugin_execution_error(self, base_config_data, mock_plugin_setup):
        mock_find_plugin, mock_get_plugin_class = mock_plugin_setup

        class ErrorPlugin(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig):
                self.config = config

            def process(self, app):
                raise RuntimeError("Plugin execution failed")

        mock_module = mock.MagicMock()
        mock_find_plugin.return_value = mock_module
        mock_get_plugin_class.return_value = ErrorPlugin

        base_config_data["DB"]["DATA"]["plugins"] = [{"name": "error_plugin", "config": {}}]
        config = Config.model_validate(base_config_data)

        with pytest.raises(PluginError) as excinfo:
            create_app_from_config(config)

        assert "Plugin execution failed" in str(excinfo.value)

    def test_plugin_without_implementation(self, base_config_data, mock_plugin_setup):
        mock_find_plugin, mock_get_plugin_class = mock_plugin_setup

        mock_module = mock.MagicMock()
        mock_find_plugin.return_value = mock_module
        mock_get_plugin_class.side_effect = PluginError("doesn't implement PluginBase")

        base_config_data["DB"]["DATA"]["plugins"] = [{"name": "invalid_plugin", "config": {}}]
        config = Config.model_validate(base_config_data)

        with pytest.raises(PluginError) as excinfo:
            create_app_from_config(config)

        assert "doesn't implement PluginBase" in str(excinfo.value)


class TestPluginConfigValidation:
    def test_config_plugin_error(self):
        class CustomPluginConfig(PluginBaseConfig):
            required_field: str  # Required field that will be missing

        class CustomPlugin(PluginBase[CustomPluginConfig]):
            @classmethod
            def get_config_model(cls):
                return CustomPluginConfig

            def process(self, app):
                return app

        with pytest.raises(ConfigPluginError) as excinfo:
            CustomPlugin({})

        assert "Invalid configuration" in str(excinfo.value)
        assert "required_field" in str(excinfo.value)

    def test_plugin_base_default_config_model(self):
        class MinimalPlugin(PluginBase[PluginBaseConfig]):
            def process(self, app):
                return app

        assert MinimalPlugin.get_config_model() == PluginBaseConfig

        plugin = MinimalPlugin({})
        assert isinstance(plugin.config, PluginBaseConfig)


class TestPluginLoading:
    def test_plugin_loading_success(self, base_config_data, mock_plugin_setup):
        mock_find_plugin, mock_get_plugin_class = mock_plugin_setup

        class MockPluginBase(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig):
                self.config = config

            def process(self, app):
                app.add_dynamic_body("Plugin added content")
                return app

        mock_module = mock.MagicMock()
        mock_find_plugin.return_value = mock_module
        mock_get_plugin_class.return_value = MockPluginBase

        base_config_data["DB"]["DATA"]["plugins"] = [
            {"name": "test_plugin", "config": {"setting": "value"}}
        ]
        config = Config.model_validate(base_config_data)
        app = create_app_from_config(config)

        mock_find_plugin.assert_called_once_with("test_plugin")
        assert "Plugin added content" in app.dynamic_body

    def test_multiple_plugins_loading(self, base_config_data, mock_plugin_setup):
        mock_find_plugin, mock_get_plugin_class = mock_plugin_setup

        class FirstPlugin(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig):
                self.config = config

            def process(self, app):
                app.add_dynamic_body("First plugin content")
                return app

        class SecondPlugin(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig):
                self.config = config

            def process(self, app):
                app.add_dynamic_head("Second plugin content")
                return app

        mock_find_plugin.side_effect = [mock.MagicMock(), mock.MagicMock()]
        mock_get_plugin_class.side_effect = [FirstPlugin, SecondPlugin]

        base_config_data["DB"]["DATA"]["plugins"] = [
            {"name": "first_plugin", "config": {"setting": "one"}},
            {"name": "second_plugin", "config": {"setting": "two"}},
        ]

        config = Config.model_validate(base_config_data)
        app = create_app_from_config(config)

        assert mock_find_plugin.call_count == 2
        assert "First plugin content" in app.dynamic_body
        assert "Second plugin content" in app.dynamic_head

    def test_real_fake_plugin_loading(self, base_config_data):
        with mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find_plugin:
            mock_find_plugin.return_value = fake_plugin

            base_config_data["DB"]["DATA"]["plugins"] = [
                {"name": "fake-plugin", "config": {"test_value": "custom_value"}}
            ]
            config = Config.model_validate(base_config_data)
            app = create_app_from_config(config)

            assert hasattr(app, "test_value")
            # TODO fix linting problem with expanding engine with plugins
            assert app.test_value == "custom_value"  # type: ignore

            mock_find_plugin.assert_called_once_with("fake-plugin")
