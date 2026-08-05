import threading
from unittest.mock import Mock, patch

import pytest
from gql import Client

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
    with patch("platzky.db.graph_ql_db.Client", return_value=mock_client):
        db = GraphQL(
            "https://test.endpoint", "test_token"
        )  # NOSONAR - hardcoded token acceptable in tests
        db.client  # trigger lazy construction now, while Client is patched
    return db


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
        patch("platzky.db.graph_ql_db.AIOHTTPTransport") as mock_transport,
        patch("platzky.db.graph_ql_db.Client", return_value=mock_client) as mock_client_class,
    ):
        db = GraphQL(
            "https://test.endpoint", "test_token"
        )  # NOSONAR - hardcoded token acceptable in tests

        assert db.client == mock_client  # client is built lazily, on first access
        mock_transport.assert_called_once_with(
            url="https://test.endpoint", headers={"Authorization": "bearer test_token"}
        )
        mock_client_class.assert_called_once()
        assert db.module_name == "graph_ql_db"
        assert db.db_name == "GraphQLDb"


def test_graph_ql_client_is_per_thread():
    db = GraphQL(
        "https://test.endpoint", "test_token"
    )  # NOSONAR - hardcoded token acceptable in tests

    main_thread_client = db.client
    other_thread_client: list[Client | Exception] = []

    def get_client_in_thread():
        try:
            other_thread_client.append(db.client)
        except Exception as e:
            other_thread_client.append(e)

    thread = threading.Thread(target=get_client_in_thread)
    thread.start()
    thread.join()

    assert len(other_thread_client) == 1, "Thread did not complete"
    if isinstance(other_thread_client[0], Exception):
        raise other_thread_client[0]
    assert db.client is main_thread_client
    assert other_thread_client[0] is not main_thread_client


@pytest.fixture
def graph_ql_db_with_mocked_repos(mock_client: Mock):
    """A GraphQL instance built with its blog storage, plugin, and site config
    repositories mocked out, so delegation can be verified through GraphQL's
    public API without reaching into its private attributes from the test.
    """
    with (
        patch("platzky.db.graph_ql_db.Client", return_value=mock_client),
        patch("platzky.db.graph_ql_db.GraphQLBlogStorage") as mock_blog_storage_class,
        patch("platzky.db.graph_ql_db.GraphQLPluginConfigRepository") as mock_plugins_class,
        patch("platzky.db.graph_ql_db.GraphQLSiteConfigRepository") as mock_site_config_class,
    ):
        db = GraphQL(
            "https://test.endpoint", "test_token"
        )  # NOSONAR - hardcoded token acceptable in tests
    return (
        db,
        mock_blog_storage_class.return_value,
        mock_plugins_class.return_value,
        mock_site_config_class.return_value,
    )


def test_get_all_posts_delegates_to_blog_storage(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock, Mock],
):
    db, blog_storage, _, _ = graph_ql_db_with_mocked_repos
    blog_storage.posts.get_all.return_value = ["sentinel"]

    result = db.get_all_posts("en")

    blog_storage.posts.get_all.assert_called_once_with("en")
    assert result == ["sentinel"]


def test_get_post_delegates_to_blog_storage(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock, Mock],
):
    db, blog_storage, _, _ = graph_ql_db_with_mocked_repos
    blog_storage.posts.get.return_value = "sentinel"

    result = db.get_post("test-post")

    blog_storage.posts.get.assert_called_once_with("test-post")
    assert result == "sentinel"


def test_get_page_delegates_to_blog_storage(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock, Mock],
):
    db, blog_storage, _, _ = graph_ql_db_with_mocked_repos
    blog_storage.pages.get.return_value = "sentinel"

    result = db.get_page("about")

    blog_storage.pages.get.assert_called_once_with("about")
    assert result == "sentinel"


def test_get_posts_by_tag_delegates_to_blog_storage(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock, Mock],
):
    db, blog_storage, _, _ = graph_ql_db_with_mocked_repos
    blog_storage.posts.get_by_tag.return_value = ["sentinel"]

    result = db.get_posts_by_tag("tag", "en")

    blog_storage.posts.get_by_tag.assert_called_once_with("tag", "en")
    assert result == ["sentinel"]


def test_add_comment_delegates_to_blog_storage(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock, Mock],
):
    db, blog_storage, _, _ = graph_ql_db_with_mocked_repos

    db.add_comment("John Doe", "Great post!", "test-post")

    blog_storage.posts.add_comment.assert_called_once_with("John Doe", "Great post!", "test-post")


def test_get_plugins_data_delegates_to_plugins_repository(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock, Mock],
):
    db, _, plugins_repository, _ = graph_ql_db_with_mocked_repos
    plugins_repository.get_all.return_value = {"sentinel": "config"}

    result = db.get_plugins_data()

    plugins_repository.get_all.assert_called_once()
    assert result == {"sentinel": "config"}


def test_get_site_settings_delegates_to_site_config(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock, Mock],
):
    db, _, _, site_config = graph_ql_db_with_mocked_repos
    site_config.get_site_settings.return_value = "sentinel"

    result = db.get_site_settings()

    site_config.get_site_settings.assert_called_once()
    assert result == "sentinel"


def test_get_menu_items_in_lang_delegates_to_site_config(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock, Mock],
):
    db, _, _, site_config = graph_ql_db_with_mocked_repos
    site_config.get_menu_items_in_lang.return_value = ["sentinel"]

    result = db.get_menu_items_in_lang("en")

    site_config.get_menu_items_in_lang.assert_called_once_with("en")
    assert result == ["sentinel"]


def test_get_home_page_path_delegates_to_site_config(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock, Mock],
):
    db, _, _, site_config = graph_ql_db_with_mocked_repos
    site_config.get_home_page_path.return_value = "/blog/page/about"

    result = db.get_home_page_path("en")

    site_config.get_home_page_path.assert_called_once_with("en")
    assert result == "/blog/page/about"


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
