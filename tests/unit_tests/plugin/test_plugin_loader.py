import os
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import MagicMock

import pytest

from platzky.config import Config
from platzky.engine import Engine
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
        mock.patch("platzky.plugin.plugin_loader._is_class_plugin") as mock_is_class_plugin,
    ):
        yield mock_find_plugin, mock_is_class_plugin


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

    def test_plugin_execution_error(
        self, base_config_data: dict[str, Any], mock_plugin_setup: tuple[MagicMock, MagicMock]
    ):
        mock_find_plugin, mock_is_class_plugin = mock_plugin_setup

        class ErrorPlugin(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig) -> None:
                self.config = config

            def process(self, app: Engine) -> Engine:
                app.dynamic_body += "This will fail"
                raise RuntimeError("Plugin execution failed")

        mock_module = mock.MagicMock()
        mock_find_plugin.return_value = mock_module
        mock_is_class_plugin.return_value = ErrorPlugin

        base_config_data["DB"]["DATA"]["plugins"] = [{"name": "error_plugin", "config": {}}]
        config = Config.model_validate(base_config_data)

        with pytest.raises(PluginError) as excinfo:
            create_app_from_config(config)

        assert "Plugin execution failed" in str(excinfo.value)

    def test_plugin_without_implementation(
        self, base_config_data: dict[str, Any], mock_plugin_setup: tuple[MagicMock, MagicMock]
    ):
        mock_find_plugin, mock_is_class_plugin = mock_plugin_setup

        mock_module = mock.MagicMock()
        del mock_module.process  # Module without process function

        mock_find_plugin.return_value = mock_module
        mock_is_class_plugin.return_value = None

        base_config_data["DB"]["DATA"]["plugins"] = [{"name": "invalid_plugin", "config": {}}]
        config = Config.model_validate(base_config_data)

        with pytest.raises(PluginError) as excinfo:
            create_app_from_config(config)

        assert (
            "doesn't implement either the PluginBase interface or provide a process() function"
            in str(excinfo.value)
        )


class TestPluginConfigValidation:
    def test_config_plugin_error(self):
        class CustomPluginConfig(PluginBaseConfig):
            required_field: str  # Required field that will be missing

        class CustomPlugin(PluginBase[CustomPluginConfig]):
            @classmethod
            def get_config_model(cls) -> type[CustomPluginConfig]:
                return CustomPluginConfig

            def process(self, app: Engine) -> Engine:
                return app

        with pytest.raises(ConfigPluginError) as excinfo:
            CustomPlugin({})

        assert "Invalid configuration" in str(excinfo.value)
        assert "required_field" in str(excinfo.value)

    def test_plugin_base_default_config_model(self):
        class MinimalPlugin(PluginBase[PluginBaseConfig]):
            def process(self, app: Engine) -> Engine:
                return app

        assert MinimalPlugin.get_config_model() == PluginBaseConfig

        plugin = MinimalPlugin({})
        assert isinstance(plugin.config, PluginBaseConfig)


class TestPluginLoading:
    def test_plugin_loading_success(
        self, base_config_data: dict[str, Any], mock_plugin_setup: tuple[MagicMock, MagicMock]
    ):
        mock_find_plugin, mock_is_class_plugin = mock_plugin_setup

        class MockPluginBase(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig) -> None:
                self.config = config

            def process(self, app: Engine) -> Engine:
                app.add_dynamic_body("Plugin added content")
                return app

        mock_module = mock.MagicMock()
        mock_find_plugin.return_value = mock_module
        mock_is_class_plugin.return_value = MockPluginBase

        base_config_data["DB"]["DATA"]["plugins"] = [
            {"name": "test_plugin", "config": {"setting": "value"}}
        ]
        config = Config.model_validate(base_config_data)
        app = create_app_from_config(config)

        mock_find_plugin.assert_called_once_with("test_plugin")
        assert "Plugin added content" in app.dynamic_body

    def test_multiple_plugins_loading(
        self, base_config_data: dict[str, Any], mock_plugin_setup: tuple[MagicMock, MagicMock]
    ):
        mock_find_plugin, mock_is_class_plugin = mock_plugin_setup

        class FirstPlugin(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig) -> None:
                self.config = config

            def process(self, app: Engine) -> Engine:
                app.add_dynamic_body("First plugin content")
                return app

        class SecondPlugin(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig) -> None:
                self.config = config

            def process(self, app: Engine) -> Engine:
                app.add_dynamic_head("Second plugin content")
                return app

        mock_find_plugin.side_effect = [mock.MagicMock(), mock.MagicMock()]
        mock_is_class_plugin.side_effect = [FirstPlugin, SecondPlugin]

        base_config_data["DB"]["DATA"]["plugins"] = [
            {"name": "first_plugin", "config": {"setting": "one"}},
            {"name": "second_plugin", "config": {"setting": "two"}},
        ]

        config = Config.model_validate(base_config_data)
        app = create_app_from_config(config)

        assert mock_find_plugin.call_count == 2
        assert "First plugin content" in app.dynamic_body
        assert "Second plugin content" in app.dynamic_head

    def test_legacy_plugin_processing(
        self, base_config_data: dict[str, Any], mock_plugin_setup: tuple[MagicMock, MagicMock]
    ):
        mock_find_plugin, mock_is_class_plugin = mock_plugin_setup

        mock_module = mock.MagicMock()

        def side_effect(app: Engine, _plugin_config: dict[str, object]) -> Engine:
            app.add_dynamic_body("Legacy plugin content")
            return app

        mock_module.process.side_effect = side_effect
        mock_find_plugin.return_value = mock_module
        mock_is_class_plugin.return_value = None

        base_config_data["DB"]["DATA"]["plugins"] = [
            {"name": "legacy_plugin", "config": {"setting": "legacy"}}
        ]
        config = Config.model_validate(base_config_data)
        app = create_app_from_config(config)

        mock_find_plugin.assert_called_once_with("legacy_plugin")
        mock_module.process.assert_called_once()
        assert "Legacy plugin content" in app.dynamic_body

    def test_real_fake_plugin_loading(self, base_config_data: dict[str, Any]):
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


class TestLocaleDirectorySecurity:
    """Test security validation of plugin locale directories through public API."""

    @pytest.fixture
    def temp_plugin_structure(self):
        """Create a temporary plugin directory structure for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_plugin"
            plugin_dir.mkdir()

            # Create plugin module file
            plugin_file = plugin_dir / "__init__.py"
            plugin_file.write_text("# test plugin")

            # Create a valid locale directory inside plugin
            locale_dir = plugin_dir / "locale"
            locale_dir.mkdir()

            # Create a directory outside plugin for testing path traversal
            external_dir = Path(tmpdir) / "external"
            external_dir.mkdir()

            yield {
                "plugin_dir": plugin_dir,
                "plugin_file": plugin_file,
                "locale_dir": locale_dir,
                "external_dir": external_dir,
                "tmpdir": tmpdir,
            }

    def test_valid_locale_directory_within_plugin(
        self, base_config_data: dict[str, Any], temp_plugin_structure: dict[str, Any]
    ):
        """Test that valid locale directory within plugin is accepted."""
        locale_dir = temp_plugin_structure["locale_dir"]
        plugin_file = temp_plugin_structure["plugin_file"]

        class SafePlugin(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig) -> None:
                self.config = config
                # Override __module__ and __file__ for testing
                self.__class__.__module__ = "test_plugin"

            def process(self, app: Engine) -> Engine:
                return app

            def get_locale_dir(self) -> str:
                return str(locale_dir)

        # Mock the module file location
        with (
            mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find,
            mock.patch("platzky.plugin.plugin_loader._is_class_plugin") as mock_is_class,
            mock.patch("inspect.getmodule") as mock_getmodule,
        ):
            mock_module = mock.MagicMock()
            mock_module.__file__ = str(plugin_file)
            mock_getmodule.return_value = mock_module

            mock_find.return_value = mock_module
            mock_is_class.return_value = SafePlugin

            base_config_data["DB"]["DATA"]["plugins"] = [{"name": "test_plugin", "config": {}}]
            config = Config.model_validate(base_config_data)

            # Should not raise any errors
            app = create_app_from_config(config)

            # Verify locale directory was registered
            babel_config = app.extensions.get("babel")
            assert babel_config is not None, "Babel extension should be configured"
            assert str(locale_dir) in babel_config.translation_directories

    def test_locale_directory_outside_plugin_path(
        self,
        base_config_data: dict[str, Any],
        temp_plugin_structure: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ):
        """Test that locale directory outside plugin path is rejected."""
        external_dir = temp_plugin_structure["external_dir"]
        plugin_file = temp_plugin_structure["plugin_file"]

        class MaliciousPlugin(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig) -> None:
                self.config = config
                self.__class__.__module__ = "test_plugin"

            def process(self, app: Engine) -> Engine:
                return app

            def get_locale_dir(self) -> str:
                # Try to expose a directory outside the plugin
                return str(external_dir)

        with (
            mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find,
            mock.patch("platzky.plugin.plugin_loader._is_class_plugin") as mock_is_class,
            mock.patch("inspect.getmodule") as mock_getmodule,
        ):
            mock_module = mock.MagicMock()
            mock_module.__file__ = str(plugin_file)
            mock_getmodule.return_value = mock_module

            mock_find.return_value = mock_module
            mock_is_class.return_value = MaliciousPlugin

            base_config_data["DB"]["DATA"]["plugins"] = [{"name": "malicious_plugin", "config": {}}]
            config = Config.model_validate(base_config_data)

            with caplog.at_level("WARNING"):
                app = create_app_from_config(config)

            # Verify warning was logged
            assert "path validation failed" in caplog.text

            # Verify locale directory was NOT registered
            babel_config = app.extensions.get("babel")
            assert babel_config is not None, "Babel extension should be configured"
            assert str(external_dir) not in babel_config.translation_directories

    def test_path_traversal_attack(
        self,
        base_config_data: dict[str, Any],
        temp_plugin_structure: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ):
        """Test that path traversal attempts (../) are rejected."""
        plugin_file = temp_plugin_structure["plugin_file"]

        class PathTraversalPlugin(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig) -> None:
                self.config = config
                self.__class__.__module__ = "test_plugin"

            def process(self, app: Engine) -> Engine:
                return app

            def get_locale_dir(self) -> str:
                # Try path traversal to escape plugin directory
                return os.path.join(str(plugin_file.parent), "..", "..", "etc")

        with (
            mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find,
            mock.patch("platzky.plugin.plugin_loader._is_class_plugin") as mock_is_class,
            mock.patch("inspect.getmodule") as mock_getmodule,
        ):
            mock_module = mock.MagicMock()
            mock_module.__file__ = str(plugin_file)
            mock_getmodule.return_value = mock_module

            mock_find.return_value = mock_module
            mock_is_class.return_value = PathTraversalPlugin

            base_config_data["DB"]["DATA"]["plugins"] = [{"name": "traversal_plugin", "config": {}}]
            config = Config.model_validate(base_config_data)

            with caplog.at_level("WARNING"):
                create_app_from_config(config)

            # Verify warning was logged
            assert "path validation failed" in caplog.text

    def test_symlink_attack(
        self,
        base_config_data: dict[str, Any],
        temp_plugin_structure: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ):
        """Test that symlink attacks are prevented by resolving real paths."""
        if os.name == "nt":
            pytest.skip("Symlink test not applicable on Windows without admin privileges")

        plugin_dir = temp_plugin_structure["plugin_dir"]
        plugin_file = temp_plugin_structure["plugin_file"]
        external_dir = temp_plugin_structure["external_dir"]

        # Create a symlink inside plugin pointing to external directory
        symlink_path = plugin_dir / "locale_symlink"
        try:
            symlink_path.symlink_to(external_dir)
        except OSError:
            pytest.skip("Unable to create symlinks on this system")

        class SymlinkPlugin(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig) -> None:
                self.config = config
                self.__class__.__module__ = "test_plugin"

            def process(self, app: Engine) -> Engine:
                return app

            def get_locale_dir(self) -> str:
                return str(symlink_path)

        with (
            mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find,
            mock.patch("platzky.plugin.plugin_loader._is_class_plugin") as mock_is_class,
            mock.patch("inspect.getmodule") as mock_getmodule,
        ):
            mock_module = mock.MagicMock()
            mock_module.__file__ = str(plugin_file)
            mock_getmodule.return_value = mock_module

            mock_find.return_value = mock_module
            mock_is_class.return_value = SymlinkPlugin

            base_config_data["DB"]["DATA"]["plugins"] = [{"name": "symlink_plugin", "config": {}}]
            config = Config.model_validate(base_config_data)

            with caplog.at_level("WARNING"):
                create_app_from_config(config)

            # Verify warning was logged
            # (symlink resolves to external directory)
            assert "path validation failed" in caplog.text

    def test_non_existent_directory(
        self,
        base_config_data: dict[str, Any],
        temp_plugin_structure: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ):
        """Test that non-existent directories are rejected."""
        plugin_file = temp_plugin_structure["plugin_file"]

        class NonExistentDirPlugin(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig) -> None:
                self.config = config
                self.__class__.__module__ = "test_plugin"

            def process(self, app: Engine) -> Engine:
                return app

            def get_locale_dir(self) -> str:
                return "/completely/fake/path/that/does/not/exist"

        with (
            mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find,
            mock.patch("platzky.plugin.plugin_loader._is_class_plugin") as mock_is_class,
            mock.patch("inspect.getmodule") as mock_getmodule,
        ):
            mock_module = mock.MagicMock()
            mock_module.__file__ = str(plugin_file)
            mock_getmodule.return_value = mock_module

            mock_find.return_value = mock_module
            mock_is_class.return_value = NonExistentDirPlugin

            base_config_data["DB"]["DATA"]["plugins"] = [
                {"name": "nonexistent_plugin", "config": {}}
            ]
            config = Config.model_validate(base_config_data)

            with caplog.at_level("WARNING"):
                create_app_from_config(config)

            # Verify warning was logged
            assert "path validation failed" in caplog.text

    def test_plugin_without_locale_dir(
        self, base_config_data: dict[str, Any], temp_plugin_structure: dict[str, Any]
    ):
        """Test that plugins without locale directories work normally."""
        plugin_file = temp_plugin_structure["plugin_file"]

        class NoLocalePlugin(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig) -> None:
                self.config = config
                self.__class__.__module__ = "test_plugin"

            def process(self, app: Engine) -> Engine:
                return app

            def get_locale_dir(self) -> None:
                return None  # No locale directory

        with (
            mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find,
            mock.patch("platzky.plugin.plugin_loader._is_class_plugin") as mock_is_class,
            mock.patch("inspect.getmodule") as mock_getmodule,
        ):
            mock_module = mock.MagicMock()
            mock_module.__file__ = str(plugin_file)
            mock_getmodule.return_value = mock_module

            mock_find.return_value = mock_module
            mock_is_class.return_value = NoLocalePlugin

            base_config_data["DB"]["DATA"]["plugins"] = [{"name": "no_locale_plugin", "config": {}}]
            config = Config.model_validate(base_config_data)

            # Should not raise any errors or warnings
            app = create_app_from_config(config)
            assert app is not None

    def test_plugin_module_without_file_attribute(
        self, base_config_data: dict[str, Any], caplog: pytest.LogCaptureFixture
    ):
        """Test handling of plugins where module has no __file__ attribute."""

        class NoFilePlugin(PluginBase[PluginBaseConfig]):
            def __init__(self, config: PluginBaseConfig) -> None:
                self.config = config

            def process(self, app: Engine) -> Engine:
                return app

            def get_locale_dir(self) -> str:
                return "/some/path"

        with (
            mock.patch("platzky.plugin.plugin_loader.find_plugin") as mock_find,
            mock.patch("platzky.plugin.plugin_loader._is_class_plugin") as mock_is_class,
            mock.patch("inspect.getmodule") as mock_getmodule,
        ):
            # Module without __file__ attribute (e.g., built-in modules)
            mock_module = mock.MagicMock()
            mock_module.__file__ = None
            mock_getmodule.return_value = mock_module

            mock_find.return_value = mock_module
            mock_is_class.return_value = NoFilePlugin

            base_config_data["DB"]["DATA"]["plugins"] = [{"name": "no_file_plugin", "config": {}}]
            config = Config.model_validate(base_config_data)

            with caplog.at_level("WARNING"):
                create_app_from_config(config)

            # Verify warning was logged
            assert "path validation failed" in caplog.text
