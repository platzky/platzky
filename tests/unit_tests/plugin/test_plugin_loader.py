import os
from unittest import mock

import pytest

from platzky.config import Config
from platzky.platzky import create_app_from_config
from platzky.plugin.plugin import PluginBase, PluginBaseConfig, PluginError


def test_invalid_plugin_config():
    invalid_plugin_config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": os.getenv("SECRET_KEY", "default_secret"),
        "USE_WWW": False,
        "BLOG_PREFIX": "/",
        "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
        "DB": {
            "TYPE": "json",
            "DATA": {"plugins": [{"name": "redirections", "config": None}]},  # Invalid config
        },
    }

    config = Config.model_validate(invalid_plugin_config_data)
    with pytest.raises(PluginError):
        create_app_from_config(config)


def test_non_existent_plugin():
    non_existent_plugin_config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": os.getenv("SECRET_KEY", "default_secret"),
        "USE_WWW": False,
        "BLOG_PREFIX": "/",
        "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
        "DB": {
            "TYPE": "json",
            "DATA": {
                "plugins": [{"name": "non_existent_plugin", "config": {}}]  # Non-existent plugin
            },
        },
    }

    config = Config.model_validate(non_existent_plugin_config_data)
    with pytest.raises(PluginError):
        create_app_from_config(config)


def test_plugin_loading_success():
    # Create a mock plugin class

    class MockPluginBase(PluginBase[PluginBaseConfig]):
        def __init__(self, config: PluginBaseConfig):
            self.config = config

        def process(self, app):
            app.add_dynamic_body("Plugin added content")
            return app

    with (
        mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find_plugin,
        mock.patch("platzky.plugin.plugin_loader._is_class_plugin") as mock_is_class_plugin,
    ):

        # Create a mock module
        mock_module = mock.MagicMock()
        mock_find_plugin.return_value = mock_module
        mock_is_class_plugin.return_value = MockPluginBase

        # Set up test config with a plugin
        plugin_config_data = {
            "APP_NAME": "testingApp",
            "SECRET_KEY": "test_secret",
            "USE_WWW": False,
            "BLOG_PREFIX": "/",
            "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
            "DB": {
                "TYPE": "json",
                "DATA": {"plugins": [{"name": "test_plugin", "config": {"setting": "value"}}]},
            },
        }

        config = Config.model_validate(plugin_config_data)
        app = create_app_from_config(config)

        # Verify the plugin was loaded and processed
        mock_find_plugin.assert_called_once_with("test_plugin")
        assert "Plugin added content" in app.dynamic_body


def test_multiple_plugins_loading():
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

    # Mock the find_plugin and _is_class_plugin functions
    with (
        mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find_plugin,
        mock.patch("platzky.plugin.plugin_loader._is_class_plugin") as mock_is_class_plugin,
    ):

        # Configure mocks to return different values for different calls
        mock_find_plugin.side_effect = [mock.MagicMock(), mock.MagicMock()]
        mock_is_class_plugin.side_effect = [FirstPlugin, SecondPlugin]

        # Set up test config with multiple plugins
        multiple_plugins_config_data = {
            "APP_NAME": "testingApp",
            "SECRET_KEY": "test_secret",
            "USE_WWW": False,
            "BLOG_PREFIX": "/",
            "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
            "DB": {
                "TYPE": "json",
                "DATA": {
                    "plugins": [
                        {"name": "first_plugin", "config": {"setting": "one"}},
                        {"name": "second_plugin", "config": {"setting": "two"}},
                    ]
                },
            },
        }

        config = Config.model_validate(multiple_plugins_config_data)
        app = create_app_from_config(config)

        # Verify both plugins were loaded and processed
        assert mock_find_plugin.call_count == 2
        assert "First plugin content" in app.dynamic_body
        assert "Second plugin content" in app.dynamic_head


def test_plugin_execution_error():
    # Create a plugin class that raises an exception during processing

    class ErrorPlugin(PluginBase[PluginBaseConfig]):
        def __init__(self, config: PluginBaseConfig):
            self.config = config

        def process(self, app):
            raise RuntimeError("Plugin execution failed")

    # Mock the find_plugin and _is_class_plugin functions
    with (
        mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find_plugin,
        mock.patch("platzky.plugin.plugin_loader._is_class_plugin") as mock_is_class_plugin,
    ):

        mock_module = mock.MagicMock()
        mock_find_plugin.return_value = mock_module
        mock_is_class_plugin.return_value = ErrorPlugin

        # Set up test config
        plugin_config_data = {
            "APP_NAME": "testingApp",
            "SECRET_KEY": "test_secret",
            "USE_WWW": False,
            "BLOG_PREFIX": "/",
            "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
            "DB": {
                "TYPE": "json",
                "DATA": {"plugins": [{"name": "error_plugin", "config": {}}]},
            },
        }

        config = Config.model_validate(plugin_config_data)
        with pytest.raises(PluginError) as excinfo:
            create_app_from_config(config)

        assert "Plugin execution failed" in str(excinfo.value)


def test_legacy_plugin_processing():
    # Mock the find_plugin function
    with (
        mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find_plugin,
        mock.patch("platzky.plugin.plugin_loader._is_class_plugin") as mock_is_class_plugin,
    ):

        # Create a mock module with a process function but no PluginBase implementation
        mock_module = mock.MagicMock()
        mock_module.process = mock.MagicMock()

        # When the module's process function is called, modify the app
        def side_effect(app, config):
            app.add_dynamic_body("Legacy plugin content")
            return app

        mock_module.process.side_effect = side_effect

        # Return the mock module and None for _is_class_plugin
        mock_find_plugin.return_value = mock_module
        mock_is_class_plugin.return_value = None

        # Set up test config with a legacy plugin
        legacy_plugin_config_data = {
            "APP_NAME": "testingApp",
            "SECRET_KEY": "test_secret",
            "USE_WWW": False,
            "BLOG_PREFIX": "/",
            "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
            "DB": {
                "TYPE": "json",
                "DATA": {"plugins": [{"name": "legacy_plugin", "config": {"setting": "legacy"}}]},
            },
        }

        config = Config.model_validate(legacy_plugin_config_data)
        app = create_app_from_config(config)

        # Verify the legacy plugin process function was called
        mock_find_plugin.assert_called_once_with("legacy_plugin")
        mock_module.process.assert_called_once()
        assert "Legacy plugin content" in app.dynamic_body


def test_plugin_without_implementation():
    # Mock the find_plugin and _is_class_plugin functions
    with (
        mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find_plugin,
        mock.patch("platzky.plugin.plugin_loader._is_class_plugin") as mock_is_class_plugin,
    ):

        # Create a mock module without a process function or PluginBase implementation
        mock_module = mock.MagicMock()
        # Remove the process attribute to simulate a module without any implementation
        del mock_module.process

        mock_find_plugin.return_value = mock_module
        mock_is_class_plugin.return_value = None  # No class-based plugin found

        # Set up test config with a plugin
        invalid_plugin_config_data = {
            "APP_NAME": "testingApp",
            "SECRET_KEY": "test_secret",
            "USE_WWW": False,
            "BLOG_PREFIX": "/",
            "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
            "DB": {
                "TYPE": "json",
                "DATA": {"plugins": [{"name": "invalid_plugin", "config": {}}]},
            },
        }

        config = Config.model_validate(invalid_plugin_config_data)

        # The plugin should raise a PluginError
        with pytest.raises(PluginError) as excinfo:
            create_app_from_config(config)

        # Verify the error message
        assert (
            "doesn't implement either the PluginBase interface or provide a process() function"
            in str(excinfo.value)
        )


def test_real_fake_plugin_loading():
    with mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find_plugin:
        # Set up the mock to return our fake_plugin module
        from tests.unit_tests.plugin import fake_plugin

        mock_find_plugin.return_value = fake_plugin

        plugin_config_data = {
            "APP_NAME": "testingApp",
            "SECRET_KEY": "test_secret",
            "USE_WWW": False,
            "BLOG_PREFIX": "/",
            "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
            "DB": {
                "TYPE": "json",
                "DATA": {
                    "plugins": [{"name": "fake-plugin", "config": {"test_value": "custom_value"}}]
                },
            },
        }

        config = Config.model_validate(plugin_config_data)
        app = create_app_from_config(config)

        assert hasattr(app, "test_value")
        #TODO fix linting problem with expanding engine with plugins
        assert app.test_value == "custom_value"  # type: ignore

        mock_find_plugin.assert_called_once_with("fake-plugin")
