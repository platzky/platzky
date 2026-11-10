"""Contract suite: every PluginConfigRepository implementation behaves identically.

Parametrized over every backend that implements it (so far Json, Mongo) so their
handling of the shared cases -- present config, no config at all, an inactive
plugin -- can never silently drift apart.
"""

from typing import Any, Callable
from unittest.mock import Mock

import pytest

from platzky.db.json_document import JsonDocument, JsonSection
from platzky.db.json_plugin_config_repository import JsonPluginConfigRepository
from platzky.db.json_stores import MemoryStore
from platzky.db.mongo_plugin_config_repository import MongoPluginConfigRepository
from platzky.db.plugin_config_repository import PluginConfigRepository


def _json_repository(plugins: dict[str, Any]) -> PluginConfigRepository:
    return JsonPluginConfigRepository(
        JsonSection(JsonDocument(MemoryStore({"plugins": plugins})), "plugins")
    )


def _mongo_repository(plugins: dict[str, Any]) -> PluginConfigRepository:
    collection = Mock()
    collection.find_one.return_value = {"_id": "config", "data": plugins} if plugins else None
    return MongoPluginConfigRepository(collection)


@pytest.fixture(
    params=[_json_repository, _mongo_repository],
    ids=["Json", "Mongo"],
)
def make_repository(
    request: pytest.FixtureRequest,
) -> Callable[[dict[str, Any]], PluginConfigRepository]:
    return request.param


class TestPluginConfigRepositoryContract:
    def test_get_all_returns_validated_configs(
        self, make_repository: Callable[[dict[str, Any]], PluginConfigRepository]
    ):
        repository = make_repository({"my_plugin": {"is_active": True, "config": {"key": "value"}}})

        plugins = repository.get_all()

        assert plugins["my_plugin"].is_active is True
        assert plugins["my_plugin"].config == {"key": "value"}

    def test_get_all_returns_empty_dict_when_no_plugins(
        self, make_repository: Callable[[dict[str, Any]], PluginConfigRepository]
    ):
        repository = make_repository({})
        assert repository.get_all() == {}

    def test_get_all_preserves_inactive_flag(
        self, make_repository: Callable[[dict[str, Any]], PluginConfigRepository]
    ):
        repository = make_repository({"my_plugin": {"is_active": False, "config": {}}})

        plugins = repository.get_all()

        assert plugins["my_plugin"].is_active is False
