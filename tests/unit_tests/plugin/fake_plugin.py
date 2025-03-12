from platzky.plugin.plugin import PluginBase, PluginBaseConfig


class FakePluginConfig(PluginBaseConfig):
    """Configuration for FakePlugin used in tests."""
    test_value: str = "default"
    optional_value: int = 42


class FakePlugin(PluginBase[FakePluginConfig]):
    """A fake plugin implementation for testing."""
    config_model = FakePluginConfig

    def process(self, app):
        """Process the plugin with the given app."""
        app.test = self.config.test_value
        return app
