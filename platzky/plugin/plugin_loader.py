import importlib
import inspect
import logging
import os
from types import ModuleType
from typing import Any, Optional, Type

import deprecation

from platzky.engine import Engine
from platzky.plugin.plugin import PluginBase, PluginError

logger = logging.getLogger(__name__)


def find_plugin(plugin_name: str) -> ModuleType:
    """Find plugin by name and return it as module.

    Args:
        plugin_name: name of plugin to find

    Raises:
        PluginError: if plugin cannot be imported

    Returns:
        module of plugin
    """
    try:
        return importlib.import_module(f"platzky_{plugin_name}")
    except ImportError as e:
        raise PluginError(
            f"Plugin {plugin_name} not found. Ensure it's installed and follows "
            f"the 'platzky_<plugin_name>' naming convention"
        ) from e


def _is_class_plugin(plugin_module: ModuleType) -> Optional[Type[PluginBase[Any]]]:
    """Check if the plugin module contains a PluginBase implementation.

    Args:
        plugin_module: The imported plugin module

    Returns:
        The plugin class if found, None otherwise
    """
    # Look for classes in the module that inherit from PluginBase
    for _, obj in inspect.getmembers(plugin_module):
        if inspect.isclass(obj) and issubclass(obj, PluginBase) and obj != PluginBase:
            return obj
    return None


@deprecation.deprecated(
    deprecated_in="1.2.0",
    removed_in="2.0.0",
    current_version="1.2.0",
    details=(
        "Legacy plugin style using the entrypoint process() function is deprecated. "
        "Migrate to PluginBase to support plugin translations and other features. "
        "See: https://platzky.readthedocs.io/en/latest/plugins.html"
    ),
)
def _process_legacy_plugin(
    plugin_module: ModuleType, app: Engine, plugin_config: dict[str, Any], plugin_name: str
) -> Engine:
    """Process a legacy plugin using the entrypoint approach.

    DEPRECATED: This function will be removed in version 2.0.0.
    Please migrate your plugin to extend PluginBase.

    Args:
        plugin_module: The plugin module
        app: The Platzky Engine instance
        plugin_config: Plugin configuration dictionary
        plugin_name: Name of the plugin

    Returns:
        Platzky Engine with processed plugin
    """
    app = plugin_module.process(app, plugin_config)
    logger.warning(
        "Plugin '%s' uses deprecated legacy interface. "
        "This will be removed in version 2.0.0. "
        "Migrate to PluginBase: https://platzky.readthedocs.io/",
        plugin_name,
    )
    return app


def _is_safe_locale_dir(locale_dir: str, plugin_instance: PluginBase[Any]) -> bool:
    """Validate that a locale directory is safe to use.

    Prevents malicious plugins from exposing arbitrary filesystem paths
    by ensuring the locale directory is within the plugin's module directory.

    Args:
        locale_dir: Path to the locale directory
        plugin_instance: The plugin instance

    Returns:
        True if the locale directory is safe to use, False otherwise
    """
    if not os.path.isdir(locale_dir):
        return False

    module = inspect.getmodule(plugin_instance.__class__)
    if module is None or not hasattr(module, "__file__") or module.__file__ is None:
        return False

    normalized_path = os.path.normpath(locale_dir)
    if ".." in normalized_path.split(os.sep):
        logger.warning("Rejected locale path with .. components: %s", locale_dir)
        return False

    # Get canonical paths (resolve symlinks)
    locale_path = os.path.realpath(locale_dir)
    module_path = os.path.realpath(os.path.dirname(module.__file__))

    if not locale_path.startswith(module_path + os.sep):
        if locale_path != module_path:
            return False

    return True


def _register_plugin_locale(
    app: Engine, plugin_instance: PluginBase[Any], plugin_name: str
) -> None:
    """Register plugin's locale directory with Babel if it exists.

    Args:
        app: The Platzky Engine instance
        plugin_instance: The plugin instance
        plugin_name: Name of the plugin for logging
    """
    locale_dir = plugin_instance.get_locale_dir()
    if locale_dir is None:
        return

    # Validate that the locale directory is safe to use
    if not _is_safe_locale_dir(locale_dir, plugin_instance):
        logger.warning(
            "Skipping locale directory for plugin %s: path validation failed: %s",
            plugin_name,
            locale_dir,
        )
        return

    babel_config = app.extensions.get("babel")
    if babel_config and locale_dir not in babel_config.translation_directories:
        babel_config.translation_directories.append(locale_dir)
        logger.info("Registered locale directory for plugin %s: %s", plugin_name, locale_dir)


def plugify(app: Engine) -> Engine:
    """Load plugins and run their entrypoints.

    Supports both class-based plugins (PluginBase) and legacy entrypoint plugins.

    Legacy plugin support is deprecated and will be removed in version 2.0.0.

    Args:
        app: Platzky Engine instance

    Returns:
        Platzky Engine with processed plugins

    Raises:
        PluginError: if plugin processing fails
    """
    plugins_data = app.db.get_plugins_data()

    for plugin_data in plugins_data:
        plugin_config = plugin_data["config"]
        plugin_name = plugin_data["name"]

        try:
            plugin_module = find_plugin(plugin_name)

            # Check if this is a class-based plugin
            plugin_class = _is_class_plugin(plugin_module)

            if plugin_class:
                # Handle new class-based plugins
                plugin_instance = plugin_class(plugin_config)
                _register_plugin_locale(app, plugin_instance, plugin_name)
                app = plugin_instance.process(app)
                logger.info("Processed class-based plugin: %s", plugin_name)
            elif hasattr(plugin_module, "process"):
                # Handle legacy entrypoint plugins with deprecation warning
                app = _process_legacy_plugin(plugin_module, app, plugin_config, plugin_name)
            else:
                raise PluginError(
                    f"Plugin {plugin_name} doesn't implement either the PluginBase interface "
                    f"or provide a process() function"
                )

        except PluginError:
            # Re-raise PluginError directly to avoid redundant wrapping
            raise
        except Exception as e:
            logger.exception("Error processing plugin %s", plugin_name)
            raise PluginError(f"Error processing plugin {plugin_name}: {e}") from e

    return app
