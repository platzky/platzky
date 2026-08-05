from collections.abc import Iterator
from unittest.mock import Mock, patch

import pytest

from platzky.db.graphql_site_config_repository import GraphQLSiteConfigRepository


@pytest.fixture
def mock_client() -> Mock:
    return Mock()


@pytest.fixture
def repository(mock_client: Mock) -> Iterator[GraphQLSiteConfigRepository]:
    # Client stays patched for the whole test (not just fixture setup): the
    # lazy client is built on the test's first real call, so the patch must
    # still be active at that point, not just during construction.
    with patch("platzky.db.graphql_client.Client", return_value=mock_client):
        yield GraphQLSiteConfigRepository(
            "https://test.endpoint", "test_token"
        )  # NOSONAR - hardcoded token acceptable in tests


class TestGetSiteSettings:
    def test_returns_full_settings(
        self, repository: GraphQLSiteConfigRepository, mock_client: Mock
    ):
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

        settings = repository.get_site_settings()

        assert settings.logo is not None
        assert settings.logo.url == "https://example.com/logo.jpg"
        assert settings.logo.alternateText == "Alt text"
        assert settings.favicon_url == "https://example.com/favicon.ico"
        assert settings.primary_color == "#0085A1"
        assert settings.secondary_color == "#006073"
        assert settings.app_description == {"en": "Hello", "pl": "Cześć"}
        assert settings.font == ""
        mock_client.execute.assert_called_once()

    def test_returns_defaults_when_everything_empty(
        self, repository: GraphQLSiteConfigRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {
            "logos": [],
            "favicons": [],
            "themes": [],
            "applicationSetups": [],
        }

        settings = repository.get_site_settings()

        assert settings.logo is None
        assert settings.favicon_url == ""
        assert settings.primary_color == "white"
        assert settings.secondary_color == "navy"
        assert settings.app_description == {}

    def test_favicon_missing_does_not_raise(
        self, repository: GraphQLSiteConfigRepository, mock_client: Mock
    ):
        """Regression test: favicon used to crash with IndexError on an empty list."""
        mock_client.execute.return_value = {
            "logos": [],
            "favicons": [],
            "themes": [{"primaryColor": "blue"}],
            "applicationSetups": [],
        }

        settings = repository.get_site_settings()

        assert settings.favicon_url == ""


def test_get_menu_items_in_lang(repository: GraphQLSiteConfigRepository, mock_client: Mock):
    mock_client.execute.return_value = {
        "menuItems": [{"name": "Home", "url": "/"}, {"name": "About", "url": "/about"}]
    }

    menu_items = repository.get_menu_items_in_lang("en")

    assert len(menu_items) == 2
    assert menu_items[0].name == "Home"
    assert menu_items[1].url == "/about"
    mock_client.execute.assert_called_once()


def test_get_home_page_path(repository: GraphQLSiteConfigRepository, mock_client: Mock):
    mock_client.execute.return_value = {"applicationSetups": [{"homePagePath": "/blog/page/about"}]}

    assert repository.get_home_page_path("en") == "/blog/page/about"
    mock_client.execute.assert_called_once()


def test_get_home_page_path_missing(repository: GraphQLSiteConfigRepository, mock_client: Mock):
    mock_client.execute.return_value = {"applicationSetups": [{}]}

    assert repository.get_home_page_path("en") is None


def test_get_home_page_path_no_application_setups(
    repository: GraphQLSiteConfigRepository, mock_client: Mock
):
    mock_client.execute.return_value = {"applicationSetups": []}

    assert repository.get_home_page_path("en") is None
