from unittest.mock import Mock

import pytest
from gql import Client
from graphql import print_ast

from platzky.db.graphql_plugin_config_repository import GraphQLPluginConfigRepository


@pytest.fixture
def mock_client() -> Mock:
    return Mock(spec=Client)


@pytest.fixture
def repository(mock_client: Mock) -> GraphQLPluginConfigRepository:
    return GraphQLPluginConfigRepository(lambda: mock_client)


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

    def test_get_all_keeps_inactive_plugin_inactive(
        self, repository: GraphQLPluginConfigRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {
            "pluginConfigs": [{"name": "off", "is_active": False, "config": {}}]
        }

        assert repository.get_all()["off"].is_active is False

    def test_get_all_requests_more_than_default_page_size(
        self, repository: GraphQLPluginConfigRepository, mock_client: Mock
    ):
        # Hygraph returns only 10 entries by default; later plugins would be dropped.
        mock_client.execute.return_value = {"pluginConfigs": []}

        repository.get_all()

        query = print_ast(mock_client.execute.call_args.args[0].document)
        assert "pluginConfigs(stage: PUBLISHED, first: 100)" in query
