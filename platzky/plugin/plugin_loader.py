import importlib.util
import logging

from platzky.plugin.plugin import PluginError

logger = logging.getLogger(__name__)


def find_plugin(plugin_name):
    """Find plugin by name and return it as module.
    :param plugin_name: name of plugin to find
    :raises PluginError: if plugin cannot be imported
    :return: module of plugin
    """
    try:
        return importlib.import_module(f"platzky_{plugin_name}")
    except ImportError as e:
        raise PluginError(
            f"Plugin {plugin_name} not found. Ensure it's installed and follows "
            f"the 'platzky_<plugin_name>' naming convention"
        ) from e


def plugify(app):
    """Load plugins and run their entrypoints.
    :param app: Flask app
    :return: Flask app
    """

    plugins_data = app.db.get_plugins_data()

    for plugin_data in plugins_data:
        plugin_config = plugin_data["config"]
        plugin_name = plugin_data["name"]
        try:
            plugin = find_plugin(plugin_name)
            plugin.process(app, plugin_config)
        except Exception as e:
            raise PluginError(f"Error processing plugin {plugin_name}: {e}") from e

    return app
