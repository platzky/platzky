import tempfile
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import MagicMock

import pytest

from platzky.config import Config
from platzky.platzky import create_app_from_config
from platzky.plugin.notifier import Notification


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


def _make_entry_point(name: str, plugin_class: type) -> MagicMock:
    ep = MagicMock()
    ep.name = name
    ep.load.return_value = plugin_class
    return ep


class TestPluginLocaleIntegration:
    """Integration tests for plugin locale registration."""

    def test_plugin_locale_registered_during_loading(self, base_config_data: dict[str, Any]):
        """Test that locale directory is registered when plugin is loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "platzky_test_plugin"
            plugin_dir.mkdir()
            locale_dir = plugin_dir / "locale"
            locale_dir.mkdir()

            init_file = plugin_dir / "__init__.py"
            init_file.write_text("""
from platzky.plugin.notifier import NotifierPluginBase

class TestPlugin(NotifierPluginBase):
    def __init__(self, config):
        pass
    def notify(self, notification):
        pass
""")

            import importlib.util
            import sys

            spec = importlib.util.spec_from_file_location("platzky_test_plugin", str(init_file))
            assert spec is not None, "Failed to create module spec"
            plugin_module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None, "Module spec has no loader"
            sys.modules["platzky_test_plugin"] = plugin_module

            try:
                spec.loader.exec_module(plugin_module)

                ep = _make_entry_point("test_plugin", plugin_module.TestPlugin)
                base_config_data["DB"]["DATA"]["plugins"] = [{"name": "test_plugin", "config": {}}]
                config = Config.model_validate(base_config_data)

                with mock.patch("importlib.metadata.entry_points", return_value=[ep]):
                    app = create_app_from_config(config)

                babel_config = app.extensions.get("babel")
                assert babel_config is not None, "Babel extension should be configured"
                assert str(locale_dir) in babel_config.translation_directories
            finally:
                sys.modules.pop("platzky_test_plugin", None)

    def test_plugin_locale_outside_plugin_directory_rejected(
        self, base_config_data: dict[str, Any], caplog: pytest.LogCaptureFixture
    ):
        """Test that locale directories outside plugin directory are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "platzky_malicious_plugin"
            plugin_dir.mkdir()

            external_dir = Path(tmpdir) / "external_sensitive_data"
            external_dir.mkdir()

            from platzky.plugin.notifier import NotifierPluginBase

            class MaliciousPlugin(NotifierPluginBase):
                def __init__(self, config: dict[str, Any]) -> None:
                    super().__init__(config)

                def get_locale_dir(self) -> str | None:
                    return str(external_dir)

                def notify(self, notification: Notification) -> None:
                    pass  # no-op: test stub

            ep = _make_entry_point("malicious_plugin", MaliciousPlugin)
            mock_module = mock.MagicMock()
            mock_module.__file__ = str(plugin_dir / "__init__.py")
            mock_module.__name__ = MaliciousPlugin.__module__

            base_config_data["DB"]["DATA"]["plugins"] = [{"name": "malicious_plugin", "config": {}}]
            config = Config.model_validate(base_config_data)

            with (
                mock.patch("importlib.metadata.entry_points", return_value=[ep]),
                mock.patch("inspect.getmodule", return_value=mock_module),
            ):
                app = create_app_from_config(config)

            babel_config = app.extensions.get("babel")
            assert babel_config is not None
            assert str(external_dir) not in babel_config.translation_directories

            assert any(
                "path validation failed" in record.message and "malicious_plugin" in record.message
                for record in caplog.records
            )

    def test_plugin_locale_with_symlink_to_external_directory_rejected(
        self, base_config_data: dict[str, Any], caplog: pytest.LogCaptureFixture
    ):
        """Test that symlinks pointing outside plugin directory are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "platzky_symlink_plugin"
            plugin_dir.mkdir()

            external_dir = Path(tmpdir) / "external_data"
            external_dir.mkdir()

            symlink_locale = plugin_dir / "locale"
            symlink_locale.symlink_to(external_dir)

            init_file = plugin_dir / "__init__.py"
            init_file.write_text("""
from platzky.plugin.notifier import NotifierPluginBase

class SymlinkPlugin(NotifierPluginBase):
    def __init__(self, config):
        pass
    def notify(self, notification):
        pass
""")

            import importlib.util
            import sys

            spec = importlib.util.spec_from_file_location("platzky_symlink_plugin", str(init_file))
            assert spec is not None
            plugin_module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            sys.modules["platzky_symlink_plugin"] = plugin_module

            try:
                spec.loader.exec_module(plugin_module)

                ep = _make_entry_point("symlink_plugin", plugin_module.SymlinkPlugin)
                base_config_data["DB"]["DATA"]["plugins"] = [
                    {"name": "symlink_plugin", "config": {}}
                ]
                config = Config.model_validate(base_config_data)

                with mock.patch("importlib.metadata.entry_points", return_value=[ep]):
                    app = create_app_from_config(config)

                babel_config = app.extensions.get("babel")
                assert babel_config is not None
                assert str(external_dir) not in babel_config.translation_directories

                assert any("path validation failed" in record.message for record in caplog.records)
            finally:
                sys.modules.pop("platzky_symlink_plugin", None)
