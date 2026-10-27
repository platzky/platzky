"""Contract suite: every PluginConfigRepository implementation behaves identically.

Parametrized over every backend that implements it (so far only Json) so their
handling of the shared cases -- present config, no config at all, an inactive
plugin -- can never silently drift apart.
"""

from typing import Any, Callable

import pytest

from platzky.db.json_document import JsonDocument
from platzky.db.json_plugin_config_repository import JsonPluginConfigRepository
from platzky.db.json_stores import MemoryStore
from platzky.db.plugin_config_repository import PluginConfigRepository


def _json_repository(plugins: dict[str, Any]) -> PluginConfigRepository:
    return JsonPluginConfigRepository(JsonDocument(MemoryStore({"plugins": plugins})))


@pytest.fixture(
    params=[_json_repository],
    ids=["Json"],
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
