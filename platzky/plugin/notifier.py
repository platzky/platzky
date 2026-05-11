"""NotifierPluginBase capability — plugins that send notifications."""

from __future__ import annotations

from abc import ABC, abstractmethod

from platzky.attachment import AttachmentProtocol
from platzky.notification_topics import NotificationTopic
from platzky.plugin.plugin import PluginBase


class NotifierPluginBase(PluginBase, ABC):
    """Base class for notifier plugins.

    Subclasses declare which topics they want to receive via ``accepted_topics``.
    The engine enforces final routing — plugins cannot bypass user-configured
    topic restrictions.
    """

    accepted_topics: set[NotificationTopic]

    @abstractmethod
    def notify(
        self,
        message: str,
        topic: NotificationTopic,
        attachments: list[AttachmentProtocol] = [],
        receiver: str = "",
    ) -> None:
        """Send a notification.

        Args:
            message: The notification message.
            topic: The notification topic.
            attachments: Attachments to include; empty list if none.
            receiver: Target recipient identifier; empty string means broadcast.
        """
        raise NotImplementedError
