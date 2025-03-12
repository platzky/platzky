import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypeVar, Generic, Type

from pydantic import BaseModel, ConfigDict

import platzky

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
    model_config = ConfigDict(extra="forbid")  # Prevent extra fields by default


T = TypeVar('T', bound=PluginBaseConfig)


class PluginBase(Generic[T], ABC):
    """Abstract base class for plugins.

    Plugin developers must extend this class to implement their plugins.
    """
    config_model: Type[T] = PluginBaseConfig

    def __init__(self, config: Dict[str, Any]):
        try:
            self.config = self.config_model.model_validate(config)
        except Exception as e:
            raise ConfigPluginError(f"Invalid configuration: {e}") from e

    @abstractmethod
    def process(self, app: platzky.Engine) -> platzky.Engine:
        """Process the plugin with the given app.

        Args:
            app: The Flask application instance

        Returns:
            Platzky Engine with processed plugins

        Raises:
            PluginError: If plugin processing fails
        """
        pass
