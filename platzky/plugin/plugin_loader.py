import importlib.util
import inspect
import logging
from typing import Any

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


def _get_plugin_class(plugin_module: Any) -> type[PluginBase[Any]]:
    """Get the PluginBase class from a plugin module.

    Args:
        plugin_module: The imported plugin module

    Returns:
        The plugin class

    Raises:
        PluginError: If no PluginBase implementation is found
    """
    # Look for classes in the module that inherit from PluginBase
    for _, obj in inspect.getmembers(plugin_module):
        if inspect.isclass(obj) and issubclass(obj, PluginBase) and obj != PluginBase:
            return obj

    raise PluginError(
        f"Plugin module {plugin_module.__name__} doesn't implement PluginBase. "
        "All plugins must extend PluginBase."
    )


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

    babel_config = app.extensions.get("babel")
    if babel_config and locale_dir not in babel_config.translation_directories:
        babel_config.translation_directories.append(locale_dir)
        logger.info("Registered locale directory for plugin %s: %s", plugin_name, locale_dir)


def plugify(app: Engine) -> Engine:
    """Load plugins and run their entrypoints.

    All plugins must extend PluginBase.

    Args:
        app: Platzky Engine instance

    Returns:
        Platzky Engine with processed plugins

    Raises:
        PluginError: if plugin processing fails or plugin doesn't extend PluginBase
    """
    plugins_data = app.db.get_plugins_data()

    for plugin_data in plugins_data:
        plugin_config = plugin_data["config"]
        plugin_name = plugin_data["name"]

        try:
            plugin_module = find_plugin(plugin_name)
            plugin_class = _get_plugin_class(plugin_module)

            # Create plugin instance
            plugin_instance = plugin_class(plugin_config)

            # Auto-register plugin locale directory
            _register_plugin_locale(app, plugin_instance, plugin_name)

            # Process plugin
            app = plugin_instance.process(app)
            logger.info("Processed plugin: %s", plugin_name)

        except PluginError:
            # Re-raise PluginError directly to avoid redundant wrapping
            raise
        except Exception as e:
            logger.exception("Error processing plugin %s", plugin_name)
            raise PluginError(f"Error processing plugin {plugin_name}: {e}") from e

    return app
