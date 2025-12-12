import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, Optional, Type, TypeVar

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

    @classmethod
    def get_config_model(cls) -> Type[PluginBaseConfig]:
        return PluginBaseConfig

    def __init__(self, config: Dict[str, Any]):
        try:
            config_class = self.get_config_model()
            self.config = config_class.model_validate(config)
        except Exception as e:
            raise ConfigPluginError(f"Invalid configuration: {e}") from e

    def get_locale_directory(self) -> Optional[str]:
        """Get the plugin's locale directory path if it exists.

        Returns:
            Path to the locale directory if it exists, None otherwise
        """
        import inspect

        # Get the module where the plugin class is defined
        module = inspect.getmodule(self.__class__)
        if module is None or not hasattr(module, "__file__"):
            return None

        # Get the directory containing the plugin module
        plugin_dir = os.path.dirname(os.path.abspath(module.__file__))
        locale_dir = os.path.join(plugin_dir, "locale")

        # Return the path only if the directory exists
        return locale_dir if os.path.isdir(locale_dir) else None

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
