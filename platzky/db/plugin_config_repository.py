"""Protocol for plugin configuration storage.

Plugin config is app-wide bootstrap wiring, loaded once at startup by
`plugin_loader.plugify()` for every plugin type (notifiers, login, content
transformers, html injectors) -- not blog content, and not per-request site
settings either, so it's kept separate from both `BlogStorage` and site
settings.
"""

from typing import Protocol

from platzky.plugin.plugin_config import PluginConfigBase


class PluginConfigRepository(Protocol):
    """Repository for plugin configuration."""

    def get_all(self) -> dict[str, PluginConfigBase]:
        """Retrieve configuration data for all plugins, keyed by plugin name.

        Returns:
            Mapping of plugin name to its validated configuration.
        """
        ...
