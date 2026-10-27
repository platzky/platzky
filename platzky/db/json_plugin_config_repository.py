"""Plugin config repository implementation backed by a shared JSON document."""

from typing_extensions import override

from platzky.db.json_document import JsonDocument
from platzky.db.plugin_config_repository import PluginConfigRepository
from platzky.plugin.plugin_config import PluginConfigBase


class JsonPluginConfigRepository(PluginConfigRepository):
    """Plugin config repository backed by a shared, in-memory document."""

    def __init__(self, document: JsonDocument) -> None:
        """Store a reference to the shared document.

        Args:
            document: The loaded document, shared with the other JSON
                repositories. Writes go through `JsonDocument.edit()`.
        """
        self._document = document

    @override
    def get_all(self) -> dict[str, PluginConfigBase]:
        """Retrieve configuration data for all plugins, keyed by plugin name.

        Returns:
            Mapping of plugin name to its validated configuration.
        """
        return {
            name: PluginConfigBase.model_validate(cfg)
            for name, cfg in (self._document.data.get("plugins") or {}).items()
        }
