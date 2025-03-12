import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, Type, TypeVar

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
