from typing import Any

from platzky.engine import Engine
from platzky.plugin.plugin import PluginBase


class FakePlugin(PluginBase):
    """A fake plugin implementation for testing.

    This plugin simulates various plugin behaviors for testing purposes.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._test_value: str = config.get("test_value", "default")
        self.process_called = False

    def process(self, app: Engine) -> Engine:
        """Process the plugin with the given app."""
        self.process_called = True
        setattr(app, "test_value", self._test_value)
        return app
