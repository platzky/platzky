import threading
from unittest.mock import Mock, patch

import pytest

from platzky.db.exceptions import NotFoundError
from platzky.db.graph_ql_db import (
    GraphQL,
    GraphQlDbConfig,
    db_config_type,
    db_from_config,
)
from platzky.models import Post


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
        assert db.module_name == "graph_ql_db"
        assert db.db_name == "GraphQLDb"


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


@pytest.fixture
def graph_ql_db_with_mocked_repos(mock_client: Mock):
    """A GraphQL instance built with its plugin and site config
    repositories mocked out, so delegation can be verified through GraphQL's
    public API without reaching into its private attributes from the test.
    """
    with (
        patch("platzky.db.graphql_client.Client", return_value=mock_client),
        patch("platzky.db.graph_ql_db.GraphQLPluginConfigRepository") as mock_plugins_class,
        patch("platzky.db.graph_ql_db.GraphQLSiteConfigRepository") as mock_site_config_class,
    ):
        db = GraphQL(
            "https://test.endpoint", "test_token"
        )  # NOSONAR - hardcoded token acceptable in tests
    return (
        db,
        mock_plugins_class.return_value,
        mock_site_config_class.return_value,
    )


def test_get_plugins_data_delegates_to_plugin_config(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock],
):
    db, plugins_repository, _ = graph_ql_db_with_mocked_repos
    plugins_repository.get_all.return_value = {"sentinel": "config"}

    result = db.get_plugins_data()

    plugins_repository.get_all.assert_called_once()
    assert result == {"sentinel": "config"}


def test_get_site_settings_delegates_to_site_config(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock],
):
    db, _, site_config = graph_ql_db_with_mocked_repos
    site_config.get_site_settings.return_value = "sentinel"

    result = db.get_site_settings()

    site_config.get_site_settings.assert_called_once()
    assert result == "sentinel"


def test_get_menu_items_in_lang_delegates_to_site_config(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock],
):
    db, _, site_config = graph_ql_db_with_mocked_repos
    site_config.get_menu_items_in_lang.return_value = ["sentinel"]

    result = db.get_menu_items_in_lang("en")

    site_config.get_menu_items_in_lang.assert_called_once_with("en")
    assert result == ["sentinel"]


def test_get_home_page_path_delegates_to_site_config(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock],
):
    db, _, site_config = graph_ql_db_with_mocked_repos
    site_config.get_home_page_path.return_value = "/blog/page/about"

    result = db.get_home_page_path("en")

    site_config.get_home_page_path.assert_called_once_with("en")
    assert result == "/blog/page/about"


def test_get_blog_meta_delegates_to_site_config(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock],
):
    db, _, site_config = graph_ql_db_with_mocked_repos
    site_config.get_blog_meta.return_value = "sentinel"

    result = db.get_blog_meta("en")

    site_config.get_blog_meta.assert_called_once_with("en")
    assert result == "sentinel"


def test_get_footer_delegates_to_site_config(
    graph_ql_db_with_mocked_repos: tuple[GraphQL, Mock, Mock],
):
    db, _, site_config = graph_ql_db_with_mocked_repos
    site_config.get_footer.return_value = "sentinel"

    result = db.get_footer("en")

    site_config.get_footer.assert_called_once_with("en")
    assert result == "sentinel"


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


def test_facade_and_repositories_share_one_client_source(mock_client: Mock):
    with (
        patch("platzky.db.graph_ql_db.GraphQLPluginConfigRepository") as plugins_cls,
        patch("platzky.db.graph_ql_db.GraphQLSiteConfigRepository") as site_cls,
        patch("platzky.db.graphql_client.Client", return_value=mock_client),
    ):
        db = GraphQL("https://test.endpoint", "test_token")

        plugins_getter = plugins_cls.call_args.args[0]
        site_getter = site_cls.call_args.args[0]
        assert plugins_getter is site_getter
        # The facade itself goes through the very same client source.
        db.health_check()
        assert plugins_getter() is mock_client
        mock_client.execute.assert_called_once()


def test_get_all_posts(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {
        "posts": [
            {
                "createdAt": "2023-01-01",
                "author": {"name": "John Doe"},
                "contentInRichText": {"html": "<p>Test content</p>"},
                "comments": [
                    {"author": "Jane Doe", "comment": "Great post!", "createdAt": "2023-01-01"}
                ],
                "date": "2023-01-01",
                "title": "Test Post",
                "excerpt": "Test excerpt",
                "slug": "test-post",
                "tags": ["test", "example"],
                "language": "en",
                "coverImage": {
                    "alternateText": "Alt text",
                    "image": {"url": "https://example.com/image.jpg"},
                },
            }
        ]
    }
    mock_client.execute.return_value = mock_response

    posts = graph_ql_db.get_all_posts("en")

    assert len(posts) == 1
    assert isinstance(posts[0], Post)
    assert posts[0].title == "Test Post"
    assert posts[0].slug == "test-post"
    mock_client.execute.assert_called_once()


def test_get_post(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {
        "post": {
            "date": "2023-01-01",
            "language": "en",
            "title": "Test Post",
            "slug": "test-post",
            "author": {"name": "John Doe"},
            "contentInRichText": {"markdown": "Test content", "html": "<p>Test content</p>"},
            "excerpt": "Test excerpt",
            "tags": ["test", "example"],
            "coverImage": {
                "alternateText": "Alt text",
                "image": {"url": "https://example.com/image.jpg"},
            },
            "comments": [
                {"author": "Jane Doe", "comment": "Great post!", "createdAt": "2023-01-01"}
            ],
            "css": ".masthead { background: teal; }",
        }
    }
    mock_client.execute.return_value = mock_response

    post = graph_ql_db.get_post("test-post")

    assert isinstance(post, Post)
    assert post.title == "Test Post"
    assert post.slug == "test-post"
    assert post.css == ".masthead { background: teal; }"
    mock_client.execute.assert_called_once()


def test_get_post_without_css(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {
        "post": {
            "date": "2023-01-01",
            "language": "en",
            "title": "Test Post",
            "slug": "test-post",
            "author": {"name": "John Doe"},
            "contentInRichText": {"markdown": "Test content", "html": "<p>Test content</p>"},
            "excerpt": "Test excerpt",
            "tags": ["test", "example"],
            "coverImage": {
                "alternateText": "Alt text",
                "image": {"url": "https://example.com/image.jpg"},
            },
            "comments": [],
            "css": None,
        }
    }
    mock_client.execute.return_value = mock_response

    post = graph_ql_db.get_post("test-post")

    assert post.css == ""


def test_get_all_pages_is_not_supported_and_queries_nothing(
    graph_ql_db: GraphQL, mock_client: Mock
):
    assert graph_ql_db.get_all_pages("en") == []
    mock_client.execute.assert_not_called()


def test_get_page(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {
        "page": {
            "slug": "about",
            "title": "About",
            "contentInMarkdown": "About page content",
            "coverImage": {"url": "https://example.com/image.jpg"},
            "css": ".masthead { background: teal; }",
        }
    }
    mock_client.execute.return_value = mock_response

    page = graph_ql_db.get_page("about")

    assert isinstance(page, Post)  # Page is an alias for Post
    assert page.title == "About"
    assert page.contentInMarkdown == "About page content"
    assert page.css == ".masthead { background: teal; }"
    mock_client.execute.assert_called_once()


def test_get_page_without_css(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {
        "page": {
            "slug": "about",
            "title": "About",
            "contentInMarkdown": "About page content",
            "coverImage": {"url": "https://example.com/image.jpg"},
        }
    }
    mock_client.execute.return_value = mock_response

    page = graph_ql_db.get_page("about")

    assert page.css == ""


def test_get_page_not_found(graph_ql_db: GraphQL, mock_client: Mock):
    mock_client.execute.return_value = {"page": None}

    with pytest.raises(NotFoundError, match="missing"):
        graph_ql_db.get_page("missing")


def test_get_post_not_found(graph_ql_db: GraphQL, mock_client: Mock):
    mock_client.execute.return_value = {"post": None}

    with pytest.raises(NotFoundError, match="missing"):
        graph_ql_db.get_post("missing")


def test_get_posts_by_tag(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {
        "posts": [
            {
                "tags": ["test", "example"],
                "title": "Test Post",
                "slug": "test-post",
                "excerpt": "Test excerpt",
                "date": "2023-01-01",
                "coverImage": {
                    "alternateText": "Alt text",
                    "image": {"url": "https://example.com/image.jpg"},
                },
            }
        ]
    }
    mock_client.execute.return_value = mock_response

    posts = graph_ql_db.get_posts_by_tag("test", "en")

    assert len(posts) == 1
    assert isinstance(posts[0], Post)
    assert posts[0].title == "Test Post"
    assert posts[0].slug == "test-post"
    mock_client.execute.assert_called_once()


def test_add_comment(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {"createComment": {"id": "123"}}
    mock_client.execute.return_value = mock_response

    graph_ql_db.add_comment("John Doe", "Great post!", "test-post")

    mock_client.execute.assert_called_once()
    # Check that the variable values were passed correctly
    call_args = mock_client.execute.call_args[1]["variable_values"]
    assert call_args["author"] == "John Doe"
    assert call_args["comment"] == "Great post!"
    assert call_args["slug"] == "test-post"
