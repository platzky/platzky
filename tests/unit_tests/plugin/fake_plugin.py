from typing import Any

from platzky.engine import Engine
from platzky.plugin.plugin import PluginBase, PluginBaseConfig


class FakePluginConfig(PluginBaseConfig):
    """Configuration for FakePlugin used in tests."""

    test_value: str = "default"
    optional_value: int = 42


class FakePlugin(PluginBase[FakePluginConfig]):
    """A fake plugin implementation for testing.

    This plugin simulates various plugin behaviors for testing purposes.
    """

    # Type hint for config to help the type checker
    config: FakePluginConfig

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.process_called = False

    @classmethod
    def get_config_model(cls) -> type[FakePluginConfig]:
        return FakePluginConfig

    def process(self, app: Engine) -> Engine:
        """Process the plugin with the given app.

        Args:
            app: The application to process

        Returns:
            The processed application
        """
        self.process_called = True

        setattr(app, "test_value", self.config.test_value)

        return app
