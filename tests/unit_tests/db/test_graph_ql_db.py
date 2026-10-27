import threading
from typing import Any
from unittest.mock import Mock, patch

import pytest
from gql import Client
from graphql import print_ast

from platzky.db.exceptions import NotFoundError
from platzky.db.graph_ql_db import (
    GraphQL,
    GraphQlDbConfig,
    db_config_type,
    db_from_config,
)
from platzky.models import Footer, PageMeta, Post


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


def test_get_menu_items_in_lang_with_lang(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {
        "menuItems": [{"name": "Home", "url": "/"}, {"name": "About", "url": "/about"}]
    }
    mock_client.execute.return_value = mock_response

    menu_items = graph_ql_db.get_menu_items_in_lang("en")

    assert len(menu_items) == 2
    assert menu_items[0].name == "Home"
    assert menu_items[1].url == "/about"
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


def test_get_site_settings(graph_ql_db: GraphQL, mock_client: Mock):
    mock_client.execute.return_value = {
        "logos": [
            {
                "logo": {
                    "alternateText": "Alt text",
                    "image": {"url": "https://example.com/logo.jpg"},
                }
            }
        ],
        "favicons": [{"favicon": {"url": "https://example.com/favicon.ico"}}],
        "themes": [{"primaryColor": "#0085A1", "secondaryColor": "#006073"}],
        "applicationSetups": [
            {"language": "en", "applicationDescription": "Hello"},
            {"language": "pl", "applicationDescription": "Cześć"},
        ],
    }

    settings = graph_ql_db.get_site_settings()

    assert settings.logo is not None
    assert settings.logo.url == "https://example.com/logo.jpg"
    assert settings.logo.alternateText == "Alt text"
    assert settings.favicon_url == "https://example.com/favicon.ico"
    assert settings.primary_color == "#0085A1"
    assert settings.secondary_color == "#006073"
    assert settings.app_description == {"en": "Hello", "pl": "Cześć"}
    assert settings.font == ""
    mock_client.execute.assert_called_once()


def test_get_site_settings_requests_more_than_default_page_size(
    graph_ql_db: GraphQL, mock_client: Mock
):
    # Hygraph returns only 10 entries by default; descriptions for later
    # languages would be dropped.
    mock_client.execute.return_value = {"applicationSetups": []}

    graph_ql_db.get_site_settings()

    query = print_ast(mock_client.execute.call_args.args[0].document)
    assert "applicationSetups(stage: PUBLISHED, first: 100)" in query


def test_get_site_settings_defaults_when_everything_empty(graph_ql_db: GraphQL, mock_client: Mock):
    mock_client.execute.return_value = {
        "logos": [],
        "favicons": [],
        "themes": [],
        "applicationSetups": [],
    }

    settings = graph_ql_db.get_site_settings()

    assert settings.logo is None
    assert settings.favicon_url == ""
    assert settings.primary_color == "white"
    assert settings.secondary_color == "navy"
    assert settings.app_description == {}


def test_get_site_settings_favicon_missing_does_not_raise(graph_ql_db: GraphQL, mock_client: Mock):
    """Regression test: favicon used to crash with IndexError on an empty list."""
    mock_client.execute.return_value = {
        "logos": [],
        "favicons": [],
        "themes": [{"primaryColor": "blue"}],
        "applicationSetups": [],
    }

    settings = graph_ql_db.get_site_settings()

    assert settings.favicon_url == ""


@pytest.mark.parametrize(
    "result",
    [
        {
            "logos": [{"logo": None}],
            "favicons": [{"favicon": None}],
            "themes": [None],
            "applicationSetups": [],
        },
        {
            "logos": [{"logo": {"alternateText": "x", "image": None}}],
            "favicons": [None],
            "themes": [{"primaryColor": None, "secondaryColor": None}],
            "applicationSetups": [],
        },
        {"logos": None, "favicons": None, "themes": None, "applicationSetups": []},
    ],
)
def test_get_site_settings_null_nodes_fall_back_to_defaults(
    graph_ql_db: GraphQL, mock_client: Mock, result: dict[str, Any]
):
    mock_client.execute.return_value = result

    settings = graph_ql_db.get_site_settings()

    assert settings.logo is None
    assert settings.favicon_url == ""
    assert settings.primary_color == "white"
    assert settings.secondary_color == "navy"


def test_get_blog_meta_is_not_supported_and_queries_nothing(
    graph_ql_db: GraphQL, mock_client: Mock
):
    assert graph_ql_db.get_blog_meta("en") == PageMeta()
    mock_client.execute.assert_not_called()


def test_get_footer_is_not_supported_and_queries_nothing(graph_ql_db: GraphQL, mock_client: Mock):
    assert graph_ql_db.get_footer("en") == Footer()
    mock_client.execute.assert_not_called()


def test_get_home_page_path(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {"applicationSetups": [{"homePagePath": "/blog/page/about"}]}
    mock_client.execute.return_value = mock_response

    assert graph_ql_db.get_home_page_path("en") == "/blog/page/about"
    mock_client.execute.assert_called_once()


def test_get_home_page_path_missing(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {"applicationSetups": [{}]}
    mock_client.execute.return_value = mock_response

    assert graph_ql_db.get_home_page_path("en") is None


def test_get_home_page_path_no_application_setups(graph_ql_db: GraphQL, mock_client: Mock):
    mock_client.execute.return_value = {"applicationSetups": []}

    assert graph_ql_db.get_home_page_path("en") is None


def test_get_plugins_data(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {
        "pluginConfigs": [{"name": "plugin1", "is_active": True, "config": {"key": "value"}}]
    }
    mock_client.execute.return_value = mock_response

    plugins_data = graph_ql_db.get_plugins_data()

    assert len(plugins_data) == 1
    assert "plugin1" in plugins_data
    assert plugins_data["plugin1"].config == {"key": "value"}
    assert plugins_data["plugin1"].is_active is True
    mock_client.execute.assert_called_once()


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
