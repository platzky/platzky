"""Notifier plugin base class and Notification payload."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from platzky.attachment import Attachment
from platzky.notification_topics import NotificationTopic
from platzky.plugin.plugin import PluginBase

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Notification:
    """Immutable notification payload passed to notifier plugins."""

    message: str
    topic: NotificationTopic
    attachments: frozenset[Attachment] = field(default_factory=frozenset)
    receivers: frozenset[str] = field(default_factory=frozenset)


class NotifierPluginBase(PluginBase, ABC):
    """Base class for notifier plugins.

    Subclasses declare which topics they want to receive via ``accepted_topics``.
    The engine enforces final routing — plugins cannot bypass user-configured
    topic restrictions.
    """

    accepted_topics: frozenset[NotificationTopic] = frozenset()

    def _warn_if_no_capabilities(self, plugin_name: str) -> None:
        """Log if accepted_topics is empty, then delegate to super()."""
        super()._warn_if_no_capabilities(plugin_name)
        if not self.accepted_topics:
            logger.debug(
                "Plugin %s declares no accepted_topics; it will receive no notifications.",
                plugin_name,
            )

    @abstractmethod
    def notify(self, notification: Notification) -> None:
        """Send a notification.

        Args:
            notification: The notification payload.
        """
        raise NotImplementedError
