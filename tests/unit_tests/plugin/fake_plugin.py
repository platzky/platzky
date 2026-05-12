from typing import Any

from platzky.plugin.plugin import PluginBase


class FakePlugin(PluginBase):
    """A fake plugin implementation for testing."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.test_value: str = config.get("test_value", "default")
