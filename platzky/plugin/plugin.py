"""Plugin base classes for the Platzky plugin system."""

from __future__ import annotations

import inspect
import logging
import os
import types
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Generic, Optional, TypeVar

import deprecation
import jinja2.ext
from pydantic import BaseModel, ConfigDict, field_validator

from platzky.attachment import AttachmentProtocol
from platzky.models import CmsModule
from platzky.notification_topics import NotificationTopic
from platzky.shortcodes import Shortcode

if TYPE_CHECKING:
    from platzky.engine import Engine

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

    @classmethod
    def get_config_model(cls) -> type[PluginBaseConfig]:
        """Return the Pydantic config model class for this plugin."""
        return PluginBaseConfig

    def __init__(self, config: dict[str, Any]) -> None:
        try:
            config_class = self.get_config_model()
            self.config = config_class.model_validate(config)
        except Exception as e:
            raise ConfigPluginError(f"Invalid configuration: {e}") from e

    def get_sub_plugins(self) -> list[PluginBase[Any]]:
        """Return direct sub-plugins owned by this plugin.

        Override to expose sub-plugins for listing and introspection.
        Sub-plugins are the plugin's own concern — the engine does not
        register them in capability buckets automatically.
        """
        return []

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
    def process(self, app: Engine) -> Engine:
        """Apply this plugin to the app.

        Deprecated: implement a typed capability subclass instead.
        """
        return app


class NotifierBaseConfig(PluginBaseConfig):
    """Configuration for notifier plugins with optional topic filtering."""

    accepted_topics: set[NotificationTopic] = {"*"}

    @field_validator("accepted_topics", mode="before")
    @classmethod
    def coerce_to_set(cls, v: object) -> set[str]:
        """Coerce list/tuple inputs to a set."""
        if isinstance(v, (list, tuple)):
            return set(v)
        return v  # type: ignore[return-value]


N = TypeVar("N", bound=NotifierBaseConfig)


class NotifierBase(PluginBase[N], ABC):
    """Base class for notifier plugins.

    Subclasses implement notify() and are automatically registered with the engine.
    Optional topic filtering is configured via accepted_topics in the plugin config.
    """

    def accepts(self, topic: str) -> bool:
        """Return True if this notifier handles the given topic."""
        topics: set[str] = getattr(self.config, "accepted_topics", {"*"})
        return topic == "*" or "*" in topics or topic in topics

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


class LoginBase(PluginBase[T], ABC):
    """Base class for login-method plugins.

    Subclasses implement get_login_html() and are automatically registered with the engine.
    """

    @abstractmethod
    def get_login_html(self) -> str:
        """Return the HTML snippet for this login method's button/form."""


class CmsModuleBase(PluginBase[T], ABC):
    """Base class for CMS module plugins.

    Subclasses implement get_cms_module() and are automatically registered with the engine.
    """

    @abstractmethod
    def get_cms_module(self) -> CmsModule:
        """Return the CmsModule descriptor for this plugin."""


class ContentFilterBase(PluginBase[T], ABC):
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
