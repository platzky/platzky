"""Example notifier plugin — logs every notification via the standard logger."""

import logging

from platzky.notification_topics import NotificationTopic
from platzky.plugin.notifier import NotifierPluginBase

logger = logging.getLogger(__name__)


class LogNotifier(NotifierPluginBase):
    """Notifier that writes every message to the Python logger."""

    accepted_topics = {"general", "content", "security"}

    def notify(self, message: str, topic: NotificationTopic, receiver: str = "") -> None:
        """Log the notification.

        Args:
            message: Notification message.
            topic: Notification topic.
            receiver: Optional recipient; logged when non-empty.
        """
        extra = f" → {receiver}" if receiver else ""
        logger.info("[%s%s] %s", topic, extra, message)
