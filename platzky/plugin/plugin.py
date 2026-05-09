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
import jinja2.ext

from platzky.attachment import AttachmentProtocol
from platzky.models import CmsModule
from platzky.notification_topics import NotificationTopic
from platzky.shortcodes import Shortcode

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
    Implement capability-specific subclasses (NotifierBase, LoginBase, etc.)
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
            "NotifierBase, LoginBase, CmsModuleBase, or ContentFilterBase."
        ),
    )
    def process(self, app: Any) -> Any:  # noqa: ANN401
        """Apply this plugin to the app.

        Deprecated: implement a typed capability subclass instead.
        """
        return app


class NotifierBase(PluginBase, ABC):
    """Base class for notifier plugins.

    Subclasses implement notify() and set self.accepted_topics in __init__.
    Topic filtering is the plugin's own responsibility — set accepted_topics
    from config to allow user overrides.
    """

    accepted_topics: set[NotificationTopic]

    def is_handling(self, topic: str) -> bool:
        """Return True if this notifier handles the given topic."""
        return topic in self.accepted_topics

    @abstractmethod
    def notify(
        self,
        message: str,
        topic: NotificationTopic,
        attachments: list[AttachmentProtocol] | None = None,
    ) -> None:
        """Send a notification.

        Args:
            message: The notification message.
            topic: The notification topic.
            attachments: Optional list of attachments.
        """
        raise NotImplementedError


class LoginBase(PluginBase, ABC):
    """Base class for login-method plugins.

    Subclasses implement get_login_html() and are automatically registered with the engine.
    """

    @abstractmethod
    def get_login_html(self) -> str:
        """Return the HTML snippet for this login method's button/form."""


class CmsModuleBase(PluginBase, ABC):
    """Base class for CMS module plugins.

    Subclasses implement get_cms_module() and are automatically registered with the engine.
    """

    @abstractmethod
    def get_cms_module(self) -> CmsModule:
        """Return the CmsModule descriptor for this plugin."""


class ContentFilterBase(PluginBase, ABC):
    """Base class for content-filter plugins.

    Subclasses register shortcode tag handlers via get_content_tags() and/or
    extend the Jinja2 template environment with custom tags via get_jinja_extensions().

    Shortcode syntax (WordPress-style):
        ``[tagname attr="val"]content[/tagname]``  — block tag
        ``[tagname attr="val"]``                    — void tag
    """

    def get_content_tags(self) -> dict[str, Shortcode]:
        """Return ``{tag_name: Shortcode}`` for shortcode tags in post/page content.

        Each ``Shortcode`` descriptor carries the handler plus documentation metadata
        (description, attributes, example) used by the admin help page.
        """
        return {}

    def get_jinja_extensions(self) -> list[type[jinja2.ext.Extension]]:
        """Return Jinja2 extension classes to register with the template engine.

        Override to expose custom Jinja2 tags available in theme templates, e.g.:
            ``{% my_tag %}...{% endmy_tag %}``
        """
        return []
