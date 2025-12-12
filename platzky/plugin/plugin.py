import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

from platzky.platzky import Engine as PlatzkyEngine

logger = logging.getLogger(__name__)


class PluginError(Exception):
    """Exception raised for plugin-related errors."""

    pass


class ConfigPluginError(PluginError):
    """Exception raised for plugin configuration-related errors."""

    pass


class PluginBaseConfig(BaseModel):
    """Base Pydantic model for plugin configurations.

    Plugin developers should extend this class to define their own configuration schema.
    """

    model_config = ConfigDict(extra="allow")


T = TypeVar("T", bound=PluginBaseConfig)


class PluginBase(Generic[T], ABC):
    """Abstract base class for plugins.

    Plugin developers must extend this class to implement their plugins.
    """

    @staticmethod
    def get_locale_dir_from_module(plugin_module: Any) -> Optional[str]:
        """Get plugin locale directory from a module.

        Encapsulates the knowledge of how plugins organize their locale directories.

        Args:
            plugin_module: The plugin module

        Returns:
            Path to the locale directory if it exists, None otherwise
        """
        if not hasattr(plugin_module, "__file__") or plugin_module.__file__ is None:
            return None

        plugin_dir = os.path.dirname(os.path.abspath(plugin_module.__file__))
        locale_dir = os.path.join(plugin_dir, "locale")

        return locale_dir if os.path.isdir(locale_dir) else None

    @classmethod
    def get_config_model(cls) -> type[PluginBaseConfig]:
        return PluginBaseConfig

    def __init__(self, config: dict[str, Any]) -> None:
        try:
            config_class = self.get_config_model()
            self.config = config_class.model_validate(config)
        except Exception as e:
            raise ConfigPluginError(f"Invalid configuration: {e}") from e

    def get_locale_dir(self) -> Optional[str]:
        """Get this plugin's locale directory.

        Returns:
            Path to the locale directory if it exists, None otherwise
        """
        import inspect

        module = inspect.getmodule(self.__class__)
        if module is None:
            return None

        return self.get_locale_dir_from_module(module)

    @abstractmethod
    def process(self, app: PlatzkyEngine) -> PlatzkyEngine:
        """Process the plugin with the given app.

        Args:
            app: The Flask application instance

        Returns:
            Platzky Engine with processed plugins

        Raises:
            PluginError: If plugin processing fails
        """
        pass
