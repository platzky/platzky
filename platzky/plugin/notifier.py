"""Notifier plugin base classes."""

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
    def notify(self, message: str, topic: NotificationTopic, receiver: str = "") -> None:
        """Send a notification.

        Args:
            message: The notification message.
            topic: The notification topic.
            receiver: Target recipient identifier; empty string means broadcast.
        """
        raise NotImplementedError


class AttachmentNotifierPluginBase(NotifierPluginBase, ABC):
    """Notifier plugin that handles file attachments.

    Subclasses implement ``notify_with_attachments``; the engine calls it when
    attachments are present. ``notify`` delegates to it with an empty list so
    the plugin also works when no attachments are sent.
    """

    def notify(self, message: str, topic: NotificationTopic, receiver: str = "") -> None:
        """Delegate to notify_with_attachments with no attachments."""
        self.notify_with_attachments(message, topic, [], receiver)

    @abstractmethod
    def notify_with_attachments(
        self,
        message: str,
        topic: NotificationTopic,
        attachments: list[AttachmentProtocol],
        receiver: str = "",
    ) -> None:
        """Send a notification with attachments.

        Args:
            message: The notification message.
            topic: The notification topic.
            attachments: Attachments to include.
            receiver: Target recipient identifier; empty string means broadcast.
        """
        raise NotImplementedError
