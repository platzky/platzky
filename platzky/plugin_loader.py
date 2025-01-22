import importlib.util
import os
import sys
from os.path import abspath, dirname


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
    :return: module of plugin
    """

    return importlib.import_module(f"platzky_{plugin_name}")


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
            plugin = find_local_plugin(plugin_name)
        except FileNotFoundError:
            plugin = find_installed_plugin(plugin_name)

        plugin.process(app, plugin_config)

    return app
