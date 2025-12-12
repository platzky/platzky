import tempfile
from pathlib import Path
from unittest import mock

import pytest

from platzky.config import Config
from platzky.platzky import create_app_from_config


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
                import sys

                spec = importlib.util.spec_from_file_location("platzky_test_plugin", str(init_file))
                assert spec is not None, "Failed to create module spec"
                plugin_module = importlib.util.module_from_spec(spec)
                assert spec.loader is not None, "Module spec has no loader"

                # Add module to sys.modules so inspect.getmodule() can find it
                sys.modules["platzky_test_plugin"] = plugin_module

                try:
                    spec.loader.exec_module(plugin_module)

                    mock_find.return_value = plugin_module

                    base_config_data["DB"]["DATA"]["plugins"] = [
                        {"name": "test_plugin", "config": {}}
                    ]
                    config = Config.model_validate(base_config_data)
                    app = create_app_from_config(config)

                    # Check if locale directory was registered
                    babel_config = app.extensions.get("babel")
                    assert babel_config is not None, "Babel extension should be configured"
                    assert str(locale_dir) in babel_config.translation_directories
                finally:
                    # Clean up sys.modules to avoid polluting other tests
                    sys.modules.pop("platzky_test_plugin", None)
