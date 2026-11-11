"""Plugin config repository implementation backed by a section of a shared JSON document."""

from typing_extensions import override

from platzky.db.json_document import JsonSection
from platzky.db.plugin_config_repository import PluginConfigRepository
from platzky.plugin.plugin_config import PluginConfigBase


class JsonPluginConfigRepository(PluginConfigRepository):
    """Plugin config repository backed by a section of a shared, in-memory document."""

    def __init__(self, section: JsonSection) -> None:
        """Store the section.

        Args:
            section: The ``plugins`` section of the shared document, the only part of it this
                repository sees.
        """
        self._section = section

    @override
    def get_all(self) -> dict[str, PluginConfigBase]:
        """Retrieve configuration data for all plugins, keyed by plugin name.

        Returns:
            Mapping of plugin name to its validated configuration.
        """
        return {name: PluginConfigBase.model_validate(cfg) for name, cfg in self._section.items()}
