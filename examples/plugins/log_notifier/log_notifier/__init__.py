"""Example notifier plugin — logs every notification via the standard logger."""

import logging
from typing import Any

from platzky.notification_topics import NotificationTopic
from platzky.plugin.notifier import Notification, NotifierPluginBase

logger = logging.getLogger(__name__)


class LogNotifier(NotifierPluginBase):
    """Notifier that writes every message to the Python logger."""

    def __init__(self, _config: dict[str, Any]) -> None:
        super().__init__(_config)
        self.accepted_topics: frozenset[NotificationTopic] = frozenset(
            {"general", "content", "security"}
        )

    def notify(self, notification: Notification) -> None:
        """Log the notification.

        Args:
            notification: The notification payload to log.
        """
        receivers = (
            f" → {', '.join(sorted(notification.receivers))}" if notification.receivers else ""
        )
        logger.info("[%s%s] %s", notification.topic, receivers, notification.message)
