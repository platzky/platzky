from typing import Any

from platzky.plugin.notifier import Notification, NotifierPluginBase


class FakePlugin(NotifierPluginBase):
    """A fake plugin implementation for testing."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.test_value: str = config.get("test_value", "default")

    def notify(self, notification: Notification) -> None:
        pass  # no-op: test stub
