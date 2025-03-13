import os
from unittest import mock
import pytest

from platzky.config import Config
from platzky.platzky import create_app_from_config
from platzky.plugin.plugin_loader import PluginError, PluginBase

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
    class MockPluginBase(PluginBase):
        def __init__(self, config):
            self.config = config

        def process(self, app):
            app.add_dynamic_body("Plugin added content")
            return app

    # Mock the find_plugin and _is_class_plugin functions
    with mock.patch('platzky.plugin.plugin_loader.find_plugin') as mock_find_plugin, \
         mock.patch('platzky.plugin.plugin_loader._is_class_plugin') as mock_is_class_plugin:

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
                "DATA": {
                    "plugins": [{"name": "test_plugin", "config": {"setting": "value"}}]
                },
            },
        }

        config = Config.model_validate(plugin_config_data)
        app = create_app_from_config(config)

        # Verify the plugin was loaded and processed
        mock_find_plugin.assert_called_once_with("test_plugin")
        assert "Plugin added content" in app.dynamic_body


def test_multiple_plugins_loading():
    # Create two mock plugin classes
    class FirstPlugin(PluginBase):
        def __init__(self, config):
            self.config = config

        def process(self, app):
            app.add_dynamic_body("First plugin content")
            return app

    class SecondPlugin(PluginBase):
        def __init__(self, config):
            self.config = config

        def process(self, app):
            app.add_dynamic_head("Second plugin content")
            return app

    # Mock the find_plugin and _is_class_plugin functions
    with mock.patch('platzky.plugin.plugin_loader.find_plugin') as mock_find_plugin, \
         mock.patch('platzky.plugin.plugin_loader._is_class_plugin') as mock_is_class_plugin:

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
                        {"name": "second_plugin", "config": {"setting": "two"}}
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
    class ErrorPlugin(PluginBase):
        def __init__(self, config):
            self.config = config

        def process(self, app):
            raise RuntimeError("Plugin execution failed")

    # Mock the find_plugin and _is_class_plugin functions
    with mock.patch('platzky.plugin.plugin_loader.find_plugin') as mock_find_plugin, \
         mock.patch('platzky.plugin.plugin_loader._is_class_plugin') as mock_is_class_plugin:

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
                "DATA": {
                    "plugins": [{"name": "error_plugin", "config": {}}]
                },
            },
        }

        config = Config.model_validate(plugin_config_data)
        with pytest.raises(PluginError) as excinfo:
            create_app_from_config(config)

        assert "Plugin execution failed" in str(excinfo.value)


def test_legacy_plugin_processing():
    # Mock the find_plugin function
    with mock.patch('platzky.plugin.plugin_loader.find_plugin') as mock_find_plugin, \
         mock.patch('platzky.plugin.plugin_loader._is_class_plugin') as mock_is_class_plugin:

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
                "DATA": {
                    "plugins": [{"name": "legacy_plugin", "config": {"setting": "legacy"}}]
                },
            },
        }

        config = Config.model_validate(legacy_plugin_config_data)
        app = create_app_from_config(config)

        # Verify the legacy plugin process function was called
        mock_find_plugin.assert_called_once_with("legacy_plugin")
        mock_module.process.assert_called_once()
        assert "Legacy plugin content" in app.dynamic_body


def test_is_class_plugin_detection():
    with mock.patch('platzky.plugin.plugin_loader.inspect') as mock_inspect:
        from platzky.plugin.plugin_loader import _is_class_plugin

        # Create a mock plugin module
        mock_module = mock.MagicMock()

        # Mock the getmembers function to return a list of (name, object) tuples
        class MockPluginClass(PluginBase):
            def process(self, app):
                return app

        class NotAPlugin:
            pass

        # Set up the mock to return a mix of classes, including our plugin class
        mock_inspect.getmembers.return_value = [
            ('regular_function', lambda x: x),
            ('non_plugin_class', NotAPlugin),
            ('plugin_class', MockPluginClass),
            ('plugin_base', PluginBase)
        ]

        # Mock isclass and issubclass behavior
        def mock_isclass(obj):
            return obj in [NotAPlugin, MockPluginClass, PluginBase]

        def mock_issubclass(obj, class_type):
            if obj == NotAPlugin:
                return False
            elif obj == MockPluginClass:
                return True
            elif obj == PluginBase:
                return True
            return False

        mock_inspect.isclass.side_effect = mock_isclass
        mock_inspect.issubclass.side_effect = mock_issubclass

        # Execute the function
        result = _is_class_plugin(mock_module)

        # Verify that inspect.getmembers was called correctly
        mock_inspect.getmembers.assert_called_once_with(mock_module)

        # Verify that we found our plugin class
        assert result == MockPluginClass

        # Test case where no plugin class exists
        mock_inspect.getmembers.return_value = [
            ('regular_function', lambda x: x),
            ('non_plugin_class', NotAPlugin),
            ('plugin_base', PluginBase)
        ]

        result = _is_class_plugin(mock_module)
        assert result is None

def test_plugin_without_implementation():
    # Mock the find_plugin and _is_class_plugin functions
    with mock.patch('platzky.plugin.plugin_loader.find_plugin') as mock_find_plugin, \
         mock.patch('platzky.plugin.plugin_loader._is_class_plugin') as mock_is_class_plugin:

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
                "DATA": {
                    "plugins": [{"name": "invalid_plugin", "config": {}}]
                },
            },
        }

        config = Config.model_validate(invalid_plugin_config_data)

        # The plugin should raise a PluginError
        with pytest.raises(PluginError) as excinfo:
            create_app_from_config(config)

        # Verify the error message
        assert "doesn't implement either the PluginBase interface or provide a process() function" in str(excinfo.value)