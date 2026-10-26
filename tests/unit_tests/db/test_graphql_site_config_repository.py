from typing import Any
from unittest.mock import Mock

import pytest

from platzky.db.graphql_site_config_repository import GraphQLSiteConfigRepository
from platzky.models import Footer, PageMeta


@pytest.fixture
def mock_client() -> Mock:
    return Mock()


@pytest.fixture
def repository(mock_client: Mock) -> GraphQLSiteConfigRepository:
    return GraphQLSiteConfigRepository(lambda: mock_client)


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


class TestNullRelationNodes:
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
    def test_null_nodes_fall_back_to_defaults(
        self,
        repository: GraphQLSiteConfigRepository,
        mock_client: Mock,
        result: dict[str, Any],
    ):
        mock_client.execute.return_value = result

        settings = repository.get_site_settings()

        assert settings.logo is None
        assert settings.favicon_url == ""
        assert settings.primary_color == "white"
        assert settings.secondary_color == "navy"


def test_null_application_description_falls_back_to_empty_string(
    repository: GraphQLSiteConfigRepository, mock_client: Mock
):
    mock_client.execute.return_value = {
        "logos": [],
        "favicons": [],
        "themes": [],
        "applicationSetups": [{"language": "en", "applicationDescription": None}],
    }

    assert repository.get_site_settings().app_description == {"en": ""}


def test_null_application_setups_is_treated_as_empty(
    repository: GraphQLSiteConfigRepository, mock_client: Mock
):
    mock_client.execute.return_value = {
        "logos": [],
        "favicons": [],
        "themes": [],
        "applicationSetups": None,
    }

    assert repository.get_site_settings().app_description == {}


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


def test_get_blog_meta_is_not_supported_and_queries_nothing(
    repository: GraphQLSiteConfigRepository, mock_client: Mock
):
    assert repository.get_blog_meta("en") == PageMeta()
    mock_client.execute.assert_not_called()


def test_get_footer_is_not_supported_and_queries_nothing(
    repository: GraphQLSiteConfigRepository, mock_client: Mock
):
    assert repository.get_footer("en") == Footer()
    mock_client.execute.assert_not_called()
