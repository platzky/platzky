import threading
from unittest.mock import Mock, patch

import pytest

from platzky.db.graph_ql_db import (
    GraphQL,
    GraphQlDbConfig,
    db_config_type,
    db_from_config,
)


@pytest.fixture
def mock_client():
    client = Mock()
    return client


@pytest.fixture
def graph_ql_db(mock_client: Mock):
    with patch("platzky.db.graphql_client.Client", return_value=mock_client):
        yield GraphQL(
            "https://test.endpoint", "test_token"
        )  # NOSONAR - hardcoded token acceptable in tests


def test_db_config_type():
    assert db_config_type() == GraphQlDbConfig


def test_graph_ql_db_config():
    config = GraphQlDbConfig.model_validate(
        {"TYPE": "graph_ql_db", "CMS_ENDPOINT": "https://test.endpoint", "CMS_TOKEN": "test_token"}
    )
    assert config.endpoint == "https://test.endpoint"
    assert config.token == "test_token"


def test_db_from_config():
    config = GraphQlDbConfig(
        TYPE="graph_ql_db", CMS_ENDPOINT="https://test.endpoint", CMS_TOKEN="test_token"
    )
    with patch("platzky.db.graph_ql_db.GraphQL") as mock_graph_ql:
        db_from_config(config)
        mock_graph_ql.assert_called_once_with("https://test.endpoint", "test_token")


def test_graph_ql_init(mock_client: Mock):
    with (
        patch("platzky.db.graphql_client.AIOHTTPTransport") as mock_transport,
        patch("platzky.db.graphql_client.Client", return_value=mock_client) as mock_client_class,
    ):
        db = GraphQL(
            "https://test.endpoint", "test_token"
        )  # NOSONAR - hardcoded token acceptable in tests

        # The client is built lazily, on first use.
        mock_client_class.assert_not_called()
        db.health_check()

        mock_transport.assert_called_once_with(
            url="https://test.endpoint", headers={"Authorization": "bearer test_token"}
        )
        mock_client_class.assert_called_once()
        mock_client.execute.assert_called_once()


def test_graph_ql_client_is_per_thread():
    clients = [Mock(), Mock(), Mock()]

    errors: list[Exception] = []

    def health_check_in_thread():
        try:
            db.health_check()
        except Exception as e:
            errors.append(e)

    with patch("platzky.db.graphql_client.Client", side_effect=clients):
        db = GraphQL(
            "https://test.endpoint", "test_token"
        )  # NOSONAR - hardcoded token acceptable in tests

        db.health_check()
        db.health_check()
        thread = threading.Thread(target=health_check_in_thread)
        thread.start()
        thread.join()

    assert not errors
    # One client for the main thread (reused across calls) and one for the other thread.
    assert clients[0].execute.call_count == 2
    assert clients[1].execute.call_count == 1
    clients[2].execute.assert_not_called()


def test_health_check_success(graph_ql_db: GraphQL, mock_client: Mock):
    """Test health check when GraphQL endpoint is accessible"""
    mock_client.execute.return_value = {"__typename": "Query"}

    # Should not raise any exception
    graph_ql_db.health_check()

    mock_client.execute.assert_called_once()


def test_health_check_failure(graph_ql_db: GraphQL, mock_client: Mock):
    """Test health check when GraphQL endpoint is not accessible"""
    mock_client.execute.side_effect = Exception("Connection failed")

    with pytest.raises(Exception, match="Connection failed"):
        graph_ql_db.health_check()


def test_facade_and_repositories_share_one_client(mock_client: Mock):
    mock_client.execute.return_value = {
        "posts": [],
        "pluginConfigs": [],
        "site": [],
        "localized": None,
    }
    with patch("platzky.db.graphql_client.Client", return_value=mock_client) as client_cls:
        db = GraphQL("https://test.endpoint", "test_token")

        db.blog.posts.get_all("en")
        db.plugin_config.get_all()
        db.site_config.get_site_settings("en")
        db.health_check()

    client_cls.assert_called_once()
    assert mock_client.execute.call_count == 4
