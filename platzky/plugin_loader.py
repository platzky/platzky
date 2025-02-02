import importlib.util
import logging
import os
import sys
from os.path import abspath, dirname

logger = logging.getLogger(__name__)


class PluginError(Exception):
    pass


# TODO remove find_local_plugin after all plugins will be extracted
def find_local_plugin(plugin_name):
    """Find plugin by name and return it as module.
    :param plugin_name: name of plugin to find
    :return: module of plugin
    """
    plugins_dir = os.path.join(dirname(abspath(__file__)), "plugins")
    module_name = plugin_name.removesuffix(".py")
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(plugins_dir, plugin_name, "entrypoint.py")
    )
    assert spec is not None
    plugin = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = plugin
    assert spec.loader is not None
    spec.loader.exec_module(plugin)
    return plugin


def find_installed_plugin(plugin_name):
    """Find plugin by name and return it as module.
    :param plugin_name: name of plugin to find
    :raises ImportError: if plugin cannot be imported or doesn't follow the naming convention
    :return: module of plugin
    """
    try:
        return importlib.import_module(f"platzky_{plugin_name}")
    except ImportError as e:
        raise ImportError(
            f"Plugin {plugin_name} not found. Ensure it's installed and follows "
            f"the 'platzky_<plugin_name>' naming convention"
        ) from e


def find_plugin(plugin_name):
    """Find plugin by name and return it as module.
    :param plugin_name: name of plugin to find
    :raises PluginError: if plugin cannot be found or imported
    :return: module of plugin
    """
    plugin = None
    try:
        plugin = find_local_plugin(plugin_name)
    except FileNotFoundError:
        logger.info(f"Local plugin {plugin_name} not found, trying installed version")
        plugin = find_installed_plugin(plugin_name)

    return plugin


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
