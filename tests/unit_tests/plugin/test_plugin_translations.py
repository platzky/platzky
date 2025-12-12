import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from platzky.config import Config
from platzky.engine import Engine
from platzky.platzky import create_app_from_config
from platzky.plugin.plugin import PluginBase, PluginBaseConfig


@pytest.fixture
def base_config_data():
    """Base configuration for tests."""
    return {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "test_secret",
        "USE_WWW": False,
        "BLOG_PREFIX": "/",
        "TRANSLATION_DIRECTORIES": [],
        "DB": {
            "TYPE": "json",
            "DATA": {"plugins": []},
        },
    }

class TestPluginBaseLocaleMethod:
    """Tests for PluginBase.get_locale_directory() method."""

    def test_get_locale_directory_exists(self):
        """Test get_locale_directory when locale directory exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a temporary plugin module file
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()
            locale_dir = plugin_dir / "locale"
            locale_dir.mkdir()

            plugin_file = plugin_dir / "plugin.py"
            plugin_file.write_text(
                """
from platzky.plugin.plugin import PluginBase, PluginBaseConfig
from platzky.engine import Engine

class TestPlugin(PluginBase[PluginBaseConfig]):
    def process(self, app: Engine) -> Engine:
        return app
"""
            )

            # Mock the module to have the correct __file__ path
            with mock.patch("inspect.getmodule") as mock_getmodule:
                mock_module = mock.MagicMock()
                mock_module.__file__ = str(plugin_file)
                mock_getmodule.return_value = mock_module

                class TestPlugin(PluginBase[PluginBaseConfig]):
                    def process(self, app: Engine) -> Engine:
                        return app

                plugin = TestPlugin({})
                result = plugin.get_locale_directory()

                assert result == str(locale_dir)
                assert result is not None
                assert os.path.isdir(result)

    def test_get_locale_directory_does_not_exist(self):
        """Test get_locale_directory when locale directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()

            plugin_file = plugin_dir / "plugin.py"
            plugin_file.write_text(
                """
from platzky.plugin.plugin import PluginBase, PluginBaseConfig
from platzky.engine import Engine

class TestPlugin(PluginBase[PluginBaseConfig]):
    def process(self, app: Engine) -> Engine:
        return app
"""
            )

            with mock.patch("inspect.getmodule") as mock_getmodule:
                mock_module = mock.MagicMock()
                mock_module.__file__ = str(plugin_file)
                mock_getmodule.return_value = mock_module

                class TestPlugin(PluginBase[PluginBaseConfig]):
                    def process(self, app: Engine) -> Engine:
                        return app

                plugin = TestPlugin({})
                result = plugin.get_locale_directory()

                assert result is None

    def test_get_locale_directory_no_module(self):
        """Test get_locale_directory when module cannot be determined."""
        with mock.patch("inspect.getmodule", return_value=None):

            class TestPlugin(PluginBase[PluginBaseConfig]):
                def process(self, app: Engine) -> Engine:
                    return app

            plugin = TestPlugin({})
            result = plugin.get_locale_directory()

            assert result is None


class TestPluginLocaleIntegration:
    """Integration tests for plugin locale registration."""

    def test_plugin_locale_registered_during_loading(self, base_config_data):
        """Test that locale directory is registered when plugin is loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create plugin with locale directory
            plugin_dir = Path(tmpdir) / "platzky_test_plugin"
            plugin_dir.mkdir()
            locale_dir = plugin_dir / "locale"
            locale_dir.mkdir()

            # Create a real plugin module
            init_file = plugin_dir / "__init__.py"
            init_file.write_text(
                """
from platzky.engine import Engine
from platzky.plugin.plugin import PluginBase, PluginBaseConfig

class TestPlugin(PluginBase[PluginBaseConfig]):
    def process(self, app: Engine) -> Engine:
        return app
"""
            )

            with mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find:
                import importlib.util

                spec = importlib.util.spec_from_file_location("platzky_test_plugin", str(init_file))
                assert spec is not None, "Failed to create module spec"
                plugin_module = importlib.util.module_from_spec(spec)
                assert spec.loader is not None, "Module spec has no loader"
                spec.loader.exec_module(plugin_module)

                mock_find.return_value = plugin_module

                base_config_data["DB"]["DATA"]["plugins"] = [{"name": "test_plugin", "config": {}}]
                config = Config.model_validate(base_config_data)
                app = create_app_from_config(config)

                # Check if locale directory was registered
                babel_config = app.extensions.get("babel")
                assert babel_config is not None, "Babel extension should be configured"
                assert str(locale_dir) in babel_config.translation_directories
