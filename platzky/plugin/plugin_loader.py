import importlib.util
import inspect
import logging
import os
from typing import Any, Optional, Type

import deprecation

from platzky.engine import Engine
from platzky.plugin.plugin import PluginBase, PluginError

logger = logging.getLogger(__name__)


def find_plugin(plugin_name: str) -> Any:
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


def _is_class_plugin(plugin_module: Any) -> Optional[Type[PluginBase[Any]]]:
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


def _register_plugin_locale(app: Engine, plugin_module: Any, plugin_name: str) -> None:
    """Register plugin's locale directory with Babel if it exists.

    Args:
        app: The Platzky Engine instance
        plugin_module: The plugin module
        plugin_name: Name of the plugin for logging
    """
    if not hasattr(plugin_module, "__file__"):
        return

    plugin_dir = os.path.dirname(os.path.abspath(plugin_module.__file__))
    locale_dir = os.path.join(plugin_dir, "locale")

    if os.path.isdir(locale_dir):
        babel_config = app.extensions.get("babel")
        if babel_config and locale_dir not in babel_config.translation_directories:
            babel_config.translation_directories.append(locale_dir)
            logger.info(f"Registered locale directory for plugin {plugin_name}: {locale_dir}")


@deprecation.deprecated(
    deprecated_in="0.3.1",
    removed_in="0.4.0",
    current_version=None,  # You should replace this with the current version
    details="Legacy plugin style using the entrypoint process() function is deprecated. "
    "Please migrate to the PluginBase interface.",
)
def _process_legacy_plugin(plugin_module, app, plugin_config, plugin_name):
    """Process a legacy plugin using the entrypoint approach."""
    app = plugin_module.process(app, plugin_config)
    logger.info(f"Processed legacy plugin: {plugin_name}")
    return app


def plugify(app: Engine) -> Engine:
    """Load plugins and run their entrypoints.

    Supports both class-based plugins (PluginBase) and legacy entrypoint plugins.

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

            # Auto-register plugin locale directory
            _register_plugin_locale(app, plugin_module, plugin_name)

            # Check if this is a class-based plugin
            plugin_class = _is_class_plugin(plugin_module)

            if plugin_class:
                # Handle new class-based plugins
                plugin_instance = plugin_class(plugin_config)
                app = plugin_instance.process(app)
                logger.info(f"Processed class-based plugin: {plugin_name}")
            elif hasattr(plugin_module, "process"):
                # Handle legacy entrypoint plugins with deprecation warning
                app = _process_legacy_plugin(plugin_module, app, plugin_config, plugin_name)
            else:
                raise PluginError(
                    f"Plugin {plugin_name} doesn't implement either the PluginBase interface "
                    f"or provide a process() function"
                )

        except Exception as e:
            logger.error(f"Error processing plugin {plugin_name}: {e}")
            raise PluginError(f"Error processing plugin {plugin_name}: {e}") from e

    return app
