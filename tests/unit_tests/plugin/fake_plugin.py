from typing import List, Optional

from platzky.engine import Engine
from platzky.plugin.plugin import PluginBase, PluginBaseConfig


class FakePluginConfig(PluginBaseConfig):
    """Configuration for FakePlugin used in tests."""

    test_value: str = "default"
    optional_value: int = 42
    add_route: bool = False
    add_template_context: bool = False
    dynamic_content: Optional[str] = None


class FakePlugin(PluginBase[FakePluginConfig]):
    """A fake plugin implementation for testing.

    This plugin simulates various plugin behaviors for testing purposes.
    """

    # Type hint for config to help the type checker
    config: FakePluginConfig

    def __init__(self, config):
        super().__init__(config)
        self.process_called = False
        self.processed_apps: List[Engine] = []

    @classmethod
    def get_config_model(cls):
        return FakePluginConfig

    def process(self, app: Engine) -> Engine:
        """Process the plugin with the given app.

        Args:
            app: The application to process

        Returns:
            The processed application
        """
        self.process_called = True
        self.processed_apps.append(app)

        setattr(app, "test_value", self.config.test_value)

        return app
