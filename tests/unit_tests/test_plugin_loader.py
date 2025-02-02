import os
import pytest
from platzky.config import Config
from platzky.platzky import create_app_from_config
from platzky.plugin_loader import PluginError

def test_invalid_plugin_config():
    invalid_plugin_config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": os.getenv("SECRET_KEY", "default_secret"),
        "USE_WWW": False,
        "BLOG_PREFIX": "/",
        "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
        "DB": {
            "TYPE": "json",
            "DATA": {
                "plugins": [
                    {"name": "redirections", "config": None}  # Invalid config
                ]
            },
        },
    }

    config = Config.model_validate(invalid_plugin_config_data)
    with pytest.raises(PluginError):
        create_app_from_config(config)

def test_non_existent_plugin():
    non_existent_plugin_config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": os.getenv("SECRET_KEY", "default_secret"),
        "USE_WWW": False,
        "BLOG_PREFIX": "/",
        "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
        "DB": {
            "TYPE": "json",
            "DATA": {
                "plugins": [
                    {"name": "non_existent_plugin", "config": {}}  # Non-existent plugin
                ]
            },
        },
    }

    config = Config.model_validate(non_existent_plugin_config_data)
    with pytest.raises(PluginError):
        create_app_from_config(config)


# TODO add test if plugin is loaded corectly but it raises an exception during its execution
# TODO test multpile plugins
