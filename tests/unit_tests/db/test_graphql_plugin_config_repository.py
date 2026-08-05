from collections.abc import Iterator
from unittest.mock import Mock, patch

import pytest

from platzky.db.graphql_plugin_config_repository import GraphQLPluginConfigRepository


@pytest.fixture
def mock_client() -> Mock:
    return Mock()


@pytest.fixture
def repository(mock_client: Mock) -> Iterator[GraphQLPluginConfigRepository]:
    # Client stays patched for the whole test (not just fixture setup): the
    # lazy client is built on the test's first real `get_all()` call, so the
    # patch must still be active at that point, not just during construction.
    with patch("platzky.db.graphql_client.Client", return_value=mock_client):
        yield GraphQLPluginConfigRepository(
            "https://test.endpoint", "test_token"
        )  # NOSONAR - hardcoded token acceptable in tests


class TestGraphQLPluginConfigRepository:
    def test_get_all_returns_validated_configs(
        self, repository: GraphQLPluginConfigRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {
            "pluginConfigs": [{"name": "plugin1", "is_active": True, "config": {"key": "value"}}]
        }

        plugins = repository.get_all()

        assert len(plugins) == 1
        assert plugins["plugin1"].config == {"key": "value"}
        assert plugins["plugin1"].is_active is True
        mock_client.execute.assert_called_once()

    def test_get_all_returns_empty_dict_when_no_plugins(
        self, repository: GraphQLPluginConfigRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {"pluginConfigs": []}
        assert repository.get_all() == {}
