from unittest.mock import Mock, patch

import pytest

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
    with patch("platzky.db.graph_ql_db.Client", return_value=mock_client):
        db = GraphQL(
            "https://test.endpoint", "test_token"
        )  # NOSONAR - hardcoded token acceptable in tests
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

        mock_transport.assert_called_once_with(
            url="https://test.endpoint", headers={"Authorization": "bearer test_token"}
        )
        mock_client_class.assert_called_once()
        assert db.client == mock_client
        assert db.module_name == "graph_ql_db"
        assert db.db_name == "GraphQLDb"


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
        }
    }
    mock_client.execute.return_value = mock_response

    post = graph_ql_db.get_post("test-post")

    assert isinstance(post, Post)
    assert post.title == "Test Post"
    assert post.slug == "test-post"
    mock_client.execute.assert_called_once()


def test_get_page(graph_ql_db: GraphQL, mock_client: Mock):
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

    assert isinstance(page, Post)  # Page is an alias for Post
    assert page.title == "About"
    assert page.contentInMarkdown == "About page content"
    mock_client.execute.assert_called_once()


def test_get_page_not_found(graph_ql_db: GraphQL, mock_client: Mock):
    mock_client.execute.return_value = {"page": None}

    with pytest.raises(ValueError, match="missing"):
        graph_ql_db.get_page("missing")


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


def test_get_font(graph_ql_db: GraphQL):
    assert graph_ql_db.get_font() == ""


def test_get_logo_url_with_logos(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {
        "logos": [
            {
                "logo": {
                    "alternateText": "Alt text",
                    "image": {"url": "https://example.com/logo.jpg"},
                }
            }
        ]
    }
    mock_client.execute.return_value = mock_response

    logo_url = graph_ql_db.get_logo_url()

    assert logo_url == "https://example.com/logo.jpg"
    mock_client.execute.assert_called_once()


def test_get_logo_url_without_logos(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {"logos": []}
    mock_client.execute.return_value = mock_response

    logo_url = graph_ql_db.get_logo_url()

    assert logo_url == ""
    mock_client.execute.assert_called_once()


def test_get_app_description(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {"applicationSetups": [{"applicationDescription": "Test description"}]}
    mock_client.execute.return_value = mock_response

    description = graph_ql_db.get_app_description("en")

    assert description == "Test description"
    mock_client.execute.assert_called_once()


def test_get_app_description_missing(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {"applicationSetups": [{}]}
    mock_client.execute.return_value = mock_response

    description = graph_ql_db.get_app_description("en")

    assert description == ""
    mock_client.execute.assert_called_once()


def test_get_favicon_url(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {"favicons": [{"favicon": {"url": "https://example.com/favicon.ico"}}]}
    mock_client.execute.return_value = mock_response

    favicon_url = graph_ql_db.get_favicon_url()

    assert favicon_url == "https://example.com/favicon.ico"
    mock_client.execute.assert_called_once()


def test_get_home_page_path(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {"applicationSetups": [{"homePagePath": "/blog/page/about"}]}
    mock_client.execute.return_value = mock_response

    assert graph_ql_db.get_home_page_path() == "/blog/page/about"
    mock_client.execute.assert_called_once()


def test_get_home_page_path_missing(graph_ql_db: GraphQL, mock_client: Mock):
    mock_response = {"applicationSetups": [{}]}
    mock_client.execute.return_value = mock_response

    assert graph_ql_db.get_home_page_path() is None


def test_get_home_page_path_no_application_setups(graph_ql_db: GraphQL, mock_client: Mock):
    mock_client.execute.return_value = {"applicationSetups": []}

    assert graph_ql_db.get_home_page_path() is None


def test_get_primary_color(graph_ql_db: GraphQL):
    color = graph_ql_db.get_primary_color()
    assert color == "white"


def test_get_secondary_color(graph_ql_db: GraphQL):
    color = graph_ql_db.get_secondary_color()
    assert color == "navy"


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
