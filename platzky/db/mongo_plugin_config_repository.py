"""Plugin config repository implementation backed by a MongoDB collection."""

from typing import Any

from pymongo.collection import Collection

from platzky.plugin.plugin_config import PluginConfigBase


class MongoPluginConfigRepository:
    """Plugin config repository backed by a MongoDB collection.

    Plugin config is stored as a single document (``{"_id": "config", "data": {...}}``)
    in the collection, unlike the flat top-level dict the JSON family uses.
    """

    def __init__(self, plugins: Collection[Any]) -> None:
        """Store a reference to the shared plugins collection.

        Args:
            plugins: The database's ``plugins`` collection.
        """
        self._plugins = plugins

    def get_all(self) -> dict[str, PluginConfigBase]:
        """Retrieve configuration data for all plugins, keyed by plugin name.

        Returns:
            Mapping of plugin name to its validated configuration.
        """
        plugins_doc = self._plugins.find_one({"_id": "config"})
        raw = plugins_doc["data"] if plugins_doc and "data" in plugins_doc else {}
        return {name: PluginConfigBase.model_validate(cfg) for name, cfg in (raw or {}).items()}
