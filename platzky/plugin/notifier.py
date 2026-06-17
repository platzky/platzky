"""Notifier plugin base class and Notification payload."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from platzky.attachment import Attachment
from platzky.notification_topics import NotificationTopic
from platzky.plugin.plugin import PluginBase
from platzky.plugin.plugin_config import PluginConfigBase


class NotifyPluginConfig(PluginConfigBase):
    """Plugin config for NotifierPluginBase plugins — carries the topic allowlist."""

    allowed_topics: frozenset[NotificationTopic] = frozenset()


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

    @abstractmethod
    def notify(self, notification: Notification) -> None:
        """Send a notification.

        Args:
            notification: The notification payload.
        """
        raise NotImplementedError
