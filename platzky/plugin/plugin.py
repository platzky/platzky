"""Plugin base classes for the Platzky plugin system."""

from __future__ import annotations

import inspect
import logging
import os
import types
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

import deprecation

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """Metadata snapshot describing a plugin."""

    name: str
    description: str


class PluginError(Exception):
    """Exception raised for plugin-related errors."""

    pass


class ConfigPluginError(PluginError):
    """Exception raised for plugin configuration-related errors."""

    pass


class PluginBase(ABC):
    """Abstract base class for plugins.

    Plugin developers must extend this class to implement their plugins.
    Implement capability-specific subclasses (NotifierPluginBase, ContentFilterPluginBase, etc.)
    rather than overriding process().
    """

    @staticmethod
    def get_locale_dir_from_module(plugin_module: types.ModuleType) -> Optional[str]:
        """Get plugin locale directory from a module.

        Args:
            plugin_module: The plugin module

        Returns:
            Path to the locale directory if it exists, None otherwise
        """
        if not hasattr(plugin_module, "__file__") or plugin_module.__file__ is None:
            return None

        plugin_dir = os.path.dirname(os.path.realpath(plugin_module.__file__))
        locale_dir = os.path.join(plugin_dir, "locale")

        return locale_dir if os.path.isdir(locale_dir) else None

    @abstractmethod
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()

    def get_info(self) -> PluginInfo:
        """Return a metadata snapshot describing this plugin.

        Override to provide a user-facing name or description.
        """
        return PluginInfo(
            name=type(self).__name__,
            description=type(self).__doc__ or "",
        )

    def get_locale_dir(self) -> Optional[str]:
        """Get this plugin's locale directory.

        Returns:
            Path to the locale directory if it exists, None otherwise
        """
        module = inspect.getmodule(self.__class__)
        if module is None:
            return None

        return self.get_locale_dir_from_module(module)

    @deprecation.deprecated(
        deprecated_in="1.5.0",
        removed_in="2.0.0",
        details=(
            "Overriding process() is deprecated. Implement a capability subclass instead: "
            "NotifierPluginBase or ContentFilterPluginBase."
        ),
    )
    def process(self, app: Any) -> Any:  # noqa: ANN401
        """Apply this plugin to the app.

        Deprecated: implement a typed capability subclass instead.
        """
        return app
