"""Plugin config repository implementation backed by a shared JSON document."""

from typing import Any

from platzky.plugin.plugin_config import PluginConfigBase


class JsonPluginConfigRepository:
    """Plugin config repository backed by a shared, in-memory document."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Store a reference to the shared document.

        Args:
            data: The loaded document, shared with whatever else (blog
                storage, site settings) reads from the same backing store.
        """
        self._data = data

    def get_all(self) -> dict[str, PluginConfigBase]:
        """Retrieve configuration data for all plugins, keyed by plugin name.

        Returns:
            Mapping of plugin name to its validated configuration.
        """
        return {
            name: PluginConfigBase.model_validate(cfg)
            for name, cfg in (self._data.get("plugins") or {}).items()
        }
