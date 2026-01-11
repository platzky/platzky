import tempfile
from pathlib import Path
from typing import Any
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

    def test_plugin_locale_registered_during_loading(self, base_config_data: Any):
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

    def test_plugin_locale_outside_plugin_directory_rejected(
        self, base_config_data: Any, caplog: Any
    ):
        """Test that locale directories outside plugin directory are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create plugin directory
            plugin_dir = Path(tmpdir) / "platzky_malicious_plugin"
            plugin_dir.mkdir()

            # Create a directory OUTSIDE the plugin to simulate attack
            external_dir = Path(tmpdir) / "external_sensitive_data"
            external_dir.mkdir()

            # Create a malicious plugin that tries to expose external directory
            init_file = plugin_dir / "__init__.py"
            init_file.write_text(
                f"""
from typing import Optional, Any
from platzky.engine import Engine
from platzky.plugin.plugin import PluginBase, PluginBaseConfig

class MaliciousPlugin(PluginBase[PluginBaseConfig]):
    def get_locale_dir(self) -> Optional[str]:
        # Malicious plugin trying to expose external directory
        return "{external_dir!s}"

    def process(self, app: Engine) -> Engine:
        return app
"""
            )

            with mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find:
                import importlib.util
                import sys

                spec = importlib.util.spec_from_file_location(
                    "platzky_malicious_plugin", str(init_file)
                )
                assert spec is not None
                plugin_module = importlib.util.module_from_spec(spec)
                assert spec.loader is not None

                sys.modules["platzky_malicious_plugin"] = plugin_module

                try:
                    spec.loader.exec_module(plugin_module)
                    mock_find.return_value = plugin_module

                    base_config_data["DB"]["DATA"]["plugins"] = [
                        {"name": "malicious_plugin", "config": {}}
                    ]
                    config = Config.model_validate(base_config_data)

                    # Should not raise an error, but should log a warning
                    app = create_app_from_config(config)

                    # Verify the malicious path was NOT registered
                    babel_config = app.extensions.get("babel")
                    assert babel_config is not None
                    assert str(external_dir) not in babel_config.translation_directories

                    # Verify a warning was logged
                    assert any(
                        "path validation failed" in record.message
                        and "malicious_plugin" in record.message
                        for record in caplog.records
                    )
                finally:
                    sys.modules.pop("platzky_malicious_plugin", None)

    def test_plugin_locale_with_symlink_to_external_directory_rejected(
        self, base_config_data: Any, caplog: Any
    ):
        """Test that symlinks pointing outside plugin directory are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create plugin directory
            plugin_dir = Path(tmpdir) / "platzky_symlink_plugin"
            plugin_dir.mkdir()

            # Create external directory
            external_dir = Path(tmpdir) / "external_data"
            external_dir.mkdir()

            # Create a symlink inside plugin that points outside
            symlink_locale = plugin_dir / "locale"
            symlink_locale.symlink_to(external_dir)

            # Create plugin
            init_file = plugin_dir / "__init__.py"
            init_file.write_text(
                """
from platzky.engine import Engine
from platzky.plugin.plugin import PluginBase, PluginBaseConfig

class SymlinkPlugin(PluginBase[PluginBaseConfig]):
    def process(self, app: Engine) -> Engine:
        return app
"""
            )

            with mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find:
                import importlib.util
                import sys

                spec = importlib.util.spec_from_file_location(
                    "platzky_symlink_plugin", str(init_file)
                )
                assert spec is not None
                plugin_module = importlib.util.module_from_spec(spec)
                assert spec.loader is not None

                sys.modules["platzky_symlink_plugin"] = plugin_module

                try:
                    spec.loader.exec_module(plugin_module)
                    mock_find.return_value = plugin_module

                    base_config_data["DB"]["DATA"]["plugins"] = [
                        {"name": "symlink_plugin", "config": {}}
                    ]
                    config = Config.model_validate(base_config_data)
                    app = create_app_from_config(config)

                    # Verify the symlinked path was NOT registered
                    # (because realpath resolves to external_dir which is outside plugin_dir)
                    babel_config = app.extensions.get("babel")
                    assert babel_config is not None
                    assert str(external_dir) not in babel_config.translation_directories

                    # Verify a warning was logged
                    assert any(
                        "path validation failed" in record.message for record in caplog.records
                    )
                finally:
                    sys.modules.pop("platzky_symlink_plugin", None)
