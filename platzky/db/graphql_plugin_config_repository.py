"""Plugin config repository implementation backed by a GraphQL (Hygraph) CMS."""

from typing import Callable

from gql import Client, gql
from typing_extensions import override

from platzky.db.plugin_config_repository import PluginConfigRepository
from platzky.plugin.plugin_config import PluginConfigBase


class GraphQLPluginConfigRepository(PluginConfigRepository):
    """Plugin config repository backed by a GraphQL CMS.

    Hygraph's ``PluginConfig`` schema only exposes ``name``, ``isActive``, and
    ``config`` (a JSON scalar) -- there's no room for a sibling field like
    ``allowed_content_types``. Authors put permission fields directly inside
    the ``config`` JSON instead; this spreads ``config``'s keys to the top
    level so the engine's capability-specific config classes
    (``ContentTransformerPluginConfig``, etc.) can find them by name.
    """

    def __init__(self, client_getter: Callable[[], Client]) -> None:
        """Store the client source.

        Args:
            client_getter: Zero-argument callable returning the GraphQL client to
                use for the current thread.
        """
        self._client_getter = client_getter

    @override
    def get_all(self) -> dict[str, PluginConfigBase]:
        """Retrieve configuration data for all plugins, keyed by plugin name.

        Returns:
            Mapping of plugin name to its validated configuration.
        """
        plugins_query = gql("""
            query MyQuery {
              pluginConfigs(stage: PUBLISHED, first: 100) {
                name
                is_active: isActive
                config
              }
            }
            """)
        raw = self._client_getter().execute(plugins_query)["pluginConfigs"]
        return {
            d["name"]: PluginConfigBase.model_validate({**(d.get("config") or {}), **d})
            for d in raw
        }
