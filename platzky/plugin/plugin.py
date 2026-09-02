"""Plugin base classes for the Platzky plugin system."""

from __future__ import annotations

import inspect
import logging
import os
import types
from abc import ABC
from dataclasses import dataclass
from typing import Any, ClassVar, Optional

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
    Implement capability-specific subclasses (NotifierPluginBase, ContentTransformerPluginBase,
    etc.) rather than overriding process().
    """

    #: Content types this plugin *defines*, added to the application's vocabulary so other
    #: plugins can accept them and site owners can grant them — the counterpart to
    #: ``ContentTransformerPluginBase.accepted_content_types``, which names what a plugin
    #: *consumes*. A plugin large enough to bring its own kind of content (a map's marker
    #: fields, a catalogue's attributes) defines it here rather than the application having
    #: to know about it: installing the plugin is enough, with no matching
    #: ``extra_content_types`` entry on the application side.
    #:
    #: Content types are read only when content is transformed, well after loading, so a
    #: plugin may contribute one whatever order it loads in.
    provides_content_types: ClassVar[frozenset[str]] = frozenset()

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

    def __init__(self, _config: dict[str, Any]) -> None:
        super().__init__()

    def get_info(self) -> PluginInfo:
        """Return a metadata snapshot describing this plugin.

        The name is the class name. By convention it matches the entry-point name the
        plugin is installed and configured under — ``RedLetterPlugin`` against
        ``red_letter`` — but nothing enforces that, so a plugin whose two differ is listed
        by its class. Override to provide a description; the docstring is used when you
        do not.
        """
        doc = type(self).__doc__
        return PluginInfo(
            name=type(self).__name__,
            description=inspect.cleandoc(doc) if doc else "",
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
