from typing import Any

from platzky.notification_topics import NotificationTopic
from platzky.plugin.notifier import NotifierPluginBase


class FakePlugin(NotifierPluginBase):
    """A fake plugin implementation for testing."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.test_value: str = config.get("test_value", "default")

    def notify(self, message: str, topic: NotificationTopic, receiver: str = "") -> None:
        pass
