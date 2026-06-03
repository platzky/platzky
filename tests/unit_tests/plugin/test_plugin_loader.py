import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any, TypedDict
from unittest import mock
from unittest.mock import MagicMock

import pytest

from platzky.config import Config
from platzky.platzky import create_app_from_config
from platzky.plugin.notifier import Notification, NotifierPluginBase
from platzky.plugin.plugin import ConfigPluginError, PluginBase, PluginError
from platzky.plugin.plugin_loader import discover_plugins
from tests.unit_tests.plugin import fake_plugin


class TempPluginStructure(TypedDict):
    """Type definition for temporary plugin directory structure."""

    plugin_dir: Path
    plugin_file: Path
    locale_dir: Path
    external_dir: Path
    tmpdir: str


@pytest.fixture
def base_config_data() -> dict[str, Any]:
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


def _make_entry_point(name: str, plugin_class: type) -> MagicMock:
    ep = MagicMock()
    ep.name = name
    ep.load.return_value = plugin_class
    return ep


class TestPluginErrors:
    def test_invalid_plugin_config(self, base_config_data: dict[str, Any]):
        base_config_data["DB"]["DATA"]["plugins"] = [{"name": "redirections", "config": None}]
        config = Config.model_validate(base_config_data)

        with pytest.raises(PluginError):
            create_app_from_config(config)

    def test_non_existent_plugin(self, base_config_data: dict[str, Any]):
        base_config_data["DB"]["DATA"]["plugins"] = [{"name": "non_existent_plugin", "config": {}}]
        config = Config.model_validate(base_config_data)

        with pytest.raises(PluginError):
            create_app_from_config(config)

    def test_plugin_execution_error(self, base_config_data: dict[str, Any]):
        class ErrorPlugin(PluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                raise RuntimeError("Plugin execution failed")

        base_config_data["DB"]["DATA"]["plugins"] = [{"name": "error_plugin", "config": {}}]
        config = Config.model_validate(base_config_data)

        ep = _make_entry_point("error_plugin", ErrorPlugin)
        with (
            mock.patch("importlib.metadata.entry_points", return_value=[ep]),
            pytest.raises(PluginError) as excinfo,
        ):
            create_app_from_config(config)

        assert "Plugin execution failed" in str(excinfo.value)


class TestPluginConfigValidation:
    def test_plugin_can_raise_config_plugin_error(self):
        class StrictPlugin(PluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                if "required_field" not in config:
                    raise ConfigPluginError("Invalid configuration: required_field missing")

        with pytest.raises(ConfigPluginError) as excinfo:
            StrictPlugin({})

        assert "required_field" in str(excinfo.value)


class TestPluginLoading:
    def test_plugin_loading_success(self, base_config_data: dict[str, Any]):
        class MockPlugin(NotifierPluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.setting = config.get("setting")

            def notify(self, notification: Notification) -> None:
                pass  # no-op: test stub

        base_config_data["DB"]["DATA"]["plugins"] = [
            {"name": "test_plugin", "config": {"setting": "value"}}
        ]
        config = Config.model_validate(base_config_data)

        ep = _make_entry_point("test_plugin", MockPlugin)
        with mock.patch("importlib.metadata.entry_points", return_value=[ep]):
            app = create_app_from_config(config)

        assert any(isinstance(p, MockPlugin) and p.setting == "value" for p in app.loaded_plugins)

    def test_multiple_plugins_loading(self, base_config_data: dict[str, Any]):
        class FirstPlugin(NotifierPluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)

            def notify(self, notification: Notification) -> None:
                pass  # no-op: test stub

        class SecondPlugin(NotifierPluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)

            def notify(self, notification: Notification) -> None:
                pass  # no-op: test stub

        base_config_data["DB"]["DATA"]["plugins"] = [
            {"name": "first_plugin", "config": {}},
            {"name": "second_plugin", "config": {}},
        ]
        config = Config.model_validate(base_config_data)

        eps = [
            _make_entry_point("first_plugin", FirstPlugin),
            _make_entry_point("second_plugin", SecondPlugin),
        ]
        with mock.patch("importlib.metadata.entry_points", return_value=eps):
            app = create_app_from_config(config)

        assert any(isinstance(p, FirstPlugin) for p in app.loaded_plugins)
        assert any(isinstance(p, SecondPlugin) for p in app.loaded_plugins)

    def test_real_fake_plugin_loading(self, base_config_data: dict[str, Any]):
        ep = _make_entry_point("fake-plugin", fake_plugin.FakePlugin)

        base_config_data["DB"]["DATA"]["plugins"] = [
            {"name": "fake-plugin", "config": {"test_value": "custom_value"}}
        ]
        config = Config.model_validate(base_config_data)
        with mock.patch("importlib.metadata.entry_points", return_value=[ep]):
            app = create_app_from_config(config)

        assert any(
            isinstance(p, fake_plugin.FakePlugin) and p.test_value == "custom_value"
            for p in app.loaded_plugins
        )


class TestLocaleDirectorySecurity:
    """Test security validation of plugin locale directories through public API."""

    @pytest.fixture
    def temp_plugin_structure(self) -> Generator[TempPluginStructure, None, None]:
        """Create a temporary plugin directory structure for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()

            plugin_file = plugin_dir / "__init__.py"
            plugin_file.write_text("# test plugin")

            locale_dir = plugin_dir / "locale"
            locale_dir.mkdir()

            external_dir = Path(tmpdir) / "external"
            external_dir.mkdir()

            yield {
                "plugin_dir": plugin_dir,
                "plugin_file": plugin_file,
                "locale_dir": locale_dir,
                "external_dir": external_dir,
                "tmpdir": tmpdir,
            }

    def _locale_plugin(self, locale_dir_value: str | None) -> type:
        """Create a minimal NotifierPluginBase subclass returning the given locale dir."""

        class LocalePlugin(NotifierPluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.__class__.__module__ = "test_plugin"

            def get_locale_dir(self) -> str | None:
                return locale_dir_value

            def notify(self, notification: Notification) -> None:
                pass  # no-op: test stub

        return LocalePlugin

    def test_valid_locale_directory_within_plugin(
        self, base_config_data: dict[str, Any], temp_plugin_structure: TempPluginStructure
    ):
        """Test that valid locale directory within plugin is accepted."""
        locale_dir = temp_plugin_structure["locale_dir"]
        plugin_file = temp_plugin_structure["plugin_file"]

        ep = _make_entry_point("test_plugin", self._locale_plugin(str(locale_dir)))
        with (
            mock.patch("importlib.metadata.entry_points", return_value=[ep]),
            mock.patch("inspect.getmodule") as mock_getmodule,
        ):
            mock_module = mock.MagicMock()
            mock_module.__file__ = str(plugin_file)
            mock_getmodule.return_value = mock_module

            base_config_data["DB"]["DATA"]["plugins"] = [{"name": "test_plugin", "config": {}}]
            config = Config.model_validate(base_config_data)

            app = create_app_from_config(config)

        babel_config = app.extensions.get("babel")
        assert babel_config is not None, "Babel extension should be configured"
        assert str(locale_dir) in babel_config.translation_directories

    def test_locale_directory_outside_plugin_path(
        self,
        base_config_data: dict[str, Any],
        temp_plugin_structure: TempPluginStructure,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test that locale directory outside plugin path is rejected."""
        external_dir = temp_plugin_structure["external_dir"]
        plugin_file = temp_plugin_structure["plugin_file"]

        ep = _make_entry_point("malicious_plugin", self._locale_plugin(str(external_dir)))
        with (
            mock.patch("importlib.metadata.entry_points", return_value=[ep]),
            mock.patch("inspect.getmodule") as mock_getmodule,
        ):
            mock_module = mock.MagicMock()
            mock_module.__file__ = str(plugin_file)
            mock_getmodule.return_value = mock_module

            base_config_data["DB"]["DATA"]["plugins"] = [{"name": "malicious_plugin", "config": {}}]
            config = Config.model_validate(base_config_data)

            with caplog.at_level("WARNING"):
                app = create_app_from_config(config)

        assert "path validation failed" in caplog.text

        babel_config = app.extensions.get("babel")
        assert babel_config is not None, "Babel extension should be configured"
        assert str(external_dir) not in babel_config.translation_directories

    def test_path_traversal_attack(
        self,
        base_config_data: dict[str, Any],
        temp_plugin_structure: TempPluginStructure,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test that path traversal attempts (../) are rejected."""
        plugin_file = temp_plugin_structure["plugin_file"]
        traversal_path = os.path.join(str(plugin_file.parent), "..", "..", "etc")

        ep = _make_entry_point("traversal_plugin", self._locale_plugin(traversal_path))
        with (
            mock.patch("importlib.metadata.entry_points", return_value=[ep]),
            mock.patch("inspect.getmodule") as mock_getmodule,
        ):
            mock_module = mock.MagicMock()
            mock_module.__file__ = str(plugin_file)
            mock_getmodule.return_value = mock_module

            base_config_data["DB"]["DATA"]["plugins"] = [{"name": "traversal_plugin", "config": {}}]
            config = Config.model_validate(base_config_data)

            with caplog.at_level("WARNING"):
                create_app_from_config(config)

        assert "path validation failed" in caplog.text

    def test_symlink_attack(
        self,
        base_config_data: dict[str, Any],
        temp_plugin_structure: TempPluginStructure,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test that symlink attacks are prevented by resolving real paths."""
        if os.name == "nt":
            pytest.skip("Symlink test not applicable on Windows without admin privileges")

        plugin_dir = temp_plugin_structure["plugin_dir"]
        plugin_file = temp_plugin_structure["plugin_file"]
        external_dir = temp_plugin_structure["external_dir"]

        symlink_path = plugin_dir / "locale_symlink"
        try:
            symlink_path.symlink_to(external_dir)
        except OSError:
            pytest.skip("Unable to create symlinks on this system")

        ep = _make_entry_point("symlink_plugin", self._locale_plugin(str(symlink_path)))
        with (
            mock.patch("importlib.metadata.entry_points", return_value=[ep]),
            mock.patch("inspect.getmodule") as mock_getmodule,
        ):
            mock_module = mock.MagicMock()
            mock_module.__file__ = str(plugin_file)
            mock_getmodule.return_value = mock_module

            base_config_data["DB"]["DATA"]["plugins"] = [{"name": "symlink_plugin", "config": {}}]
            config = Config.model_validate(base_config_data)

            with caplog.at_level("WARNING"):
                create_app_from_config(config)

        assert "path validation failed" in caplog.text

    def test_non_existent_directory(
        self,
        base_config_data: dict[str, Any],
        temp_plugin_structure: TempPluginStructure,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test that non-existent directories are rejected."""
        plugin_file = temp_plugin_structure["plugin_file"]

        ep = _make_entry_point(
            "nonexistent_plugin",
            self._locale_plugin("/completely/fake/path/that/does/not/exist"),
        )
        with (
            mock.patch("importlib.metadata.entry_points", return_value=[ep]),
            mock.patch("inspect.getmodule") as mock_getmodule,
        ):
            mock_module = mock.MagicMock()
            mock_module.__file__ = str(plugin_file)
            mock_getmodule.return_value = mock_module

            base_config_data["DB"]["DATA"]["plugins"] = [
                {"name": "nonexistent_plugin", "config": {}}
            ]
            config = Config.model_validate(base_config_data)

            with caplog.at_level("WARNING"):
                create_app_from_config(config)

        assert "path validation failed" in caplog.text

    def test_plugin_without_locale_dir(
        self, base_config_data: dict[str, Any], temp_plugin_structure: TempPluginStructure
    ):
        """Test that plugins without locale directories work normally."""
        plugin_file = temp_plugin_structure["plugin_file"]

        ep = _make_entry_point("no_locale_plugin", self._locale_plugin(None))
        with (
            mock.patch("importlib.metadata.entry_points", return_value=[ep]),
            mock.patch("inspect.getmodule") as mock_getmodule,
        ):
            mock_module = mock.MagicMock()
            mock_module.__file__ = str(plugin_file)
            mock_getmodule.return_value = mock_module

            base_config_data["DB"]["DATA"]["plugins"] = [{"name": "no_locale_plugin", "config": {}}]
            config = Config.model_validate(base_config_data)

            app = create_app_from_config(config)
            assert app is not None

    def test_plugin_module_without_file_attribute(
        self, base_config_data: dict[str, Any], caplog: pytest.LogCaptureFixture
    ):
        """Test handling of plugins where module has no __file__ attribute."""
        ep = _make_entry_point("no_file_plugin", self._locale_plugin("/some/path"))
        with (
            mock.patch("importlib.metadata.entry_points", return_value=[ep]),
            mock.patch("inspect.getmodule") as mock_getmodule,
        ):
            mock_module = mock.MagicMock()
            mock_module.__file__ = None
            mock_getmodule.return_value = mock_module

            base_config_data["DB"]["DATA"]["plugins"] = [{"name": "no_file_plugin", "config": {}}]
            config = Config.model_validate(base_config_data)

            with caplog.at_level("WARNING"):
                create_app_from_config(config)

        assert "path validation failed" in caplog.text


class TestDiscoverPlugins:
    def _make_entry_point(self, name: str, plugin_class: type) -> MagicMock:
        ep = MagicMock()
        ep.name = name
        ep.load.return_value = plugin_class
        return ep

    def test_returns_empty_dict_when_no_entry_points(self) -> None:
        with mock.patch("importlib.metadata.entry_points", return_value=[]):
            result = discover_plugins()
        assert result == {}

    def test_discovers_valid_plugin(self) -> None:
        class MyPlugin(PluginBase):
            pass

        ep = self._make_entry_point("myplugin", MyPlugin)
        with mock.patch("importlib.metadata.entry_points", return_value=[ep]):
            result = discover_plugins()

        assert result == {"myplugin": MyPlugin}

    def test_discovers_multiple_plugins(self) -> None:
        class PluginA(PluginBase):
            pass

        class PluginB(PluginBase):
            pass

        eps = [
            self._make_entry_point("plugin_a", PluginA),
            self._make_entry_point("plugin_b", PluginB),
        ]
        with mock.patch("importlib.metadata.entry_points", return_value=eps):
            result = discover_plugins()

        assert result == {"plugin_a": PluginA, "plugin_b": PluginB}

    def test_skips_non_plugin_base_entry_point(self) -> None:
        class NotAPlugin:
            pass

        ep = self._make_entry_point("bad", NotAPlugin)
        with mock.patch("importlib.metadata.entry_points", return_value=[ep]):
            result = discover_plugins()

        assert result == {}

    def test_skips_failed_entry_point_load(self) -> None:
        ep = MagicMock()
        ep.name = "broken"
        ep.load.side_effect = ImportError("missing dependency")

        with mock.patch("importlib.metadata.entry_points", return_value=[ep]):
            result = discover_plugins()

        assert result == {}

    def test_plugify_uses_entry_point_when_available(
        self, base_config_data: dict[str, Any]
    ) -> None:
        class EntryPointPlugin(NotifierPluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)

            def notify(self, notification: Notification) -> None:
                pass  # no-op: test stub

        base_config_data["DB"]["DATA"]["plugins"] = [{"name": "myplugin", "config": {}}]
        config = Config.model_validate(base_config_data)

        ep = self._make_entry_point("myplugin", EntryPointPlugin)
        with mock.patch("importlib.metadata.entry_points", return_value=[ep]):
            app = create_app_from_config(config)

        assert any(isinstance(p, EntryPointPlugin) for p in app.loaded_plugins)

    def test_plugify_raises_when_no_entry_point(self, base_config_data: dict[str, Any]) -> None:
        base_config_data["DB"]["DATA"]["plugins"] = [{"name": "missing_plugin", "config": {}}]
        config = Config.model_validate(base_config_data)

        with (
            mock.patch("importlib.metadata.entry_points", return_value=[]),
            pytest.raises(PluginError, match="missing_plugin"),
        ):
            create_app_from_config(config)
