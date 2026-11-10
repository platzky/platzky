"""GraphQL backend: the SiteConfigRepository contract plus the requests it sends."""

from collections.abc import Mapping
from typing import Any
from unittest.mock import Mock

import pytest
from gql import Client
from graphql import print_ast

from platzky.db.graphql_site_config_repository import GraphQLSiteConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository, SiteSettings
from platzky.models import Image
from tests.unit_tests.db.site_config_repository_contract import SiteConfigRepositoryContract


def _hygraph_entry(language: str | None, content: Mapping[str, Any]) -> dict[str, Any]:
    """Map a neutral entry to a Hygraph `LocalizedContent` entry (camelCase, nested logo)."""
    logo_url = content.get("logo_url")
    return {
        "language": language,
        "appName": content.get("app_name"),
        "appTitle": content.get("app_title"),
        "appDescription": content.get("app_description"),
        "logo": {"image": {"url": logo_url}} if logo_url else None,
        "blogMeta": content.get("blog_meta"),
        "footer": content.get("footer"),
        "homePagePath": content.get("home_page_path"),
        "menuItems": content.get("menu_items"),
    }


def _graphql_repository(site_content: dict[str, Any]) -> SiteConfigRepository:
    localized_content = site_content.get("localized_content", {})
    client = Mock(spec=Client)
    client.execute.return_value = {
        "localizedContents": [
            _hygraph_entry(None, site_content),
            *(_hygraph_entry(lang, content) for lang, content in localized_content.items()),
        ],
        "logos": [],
        "favicons": [{"favicon": {"url": site_content.get("favicon_url")}}],
        "themes": [
            {
                "primaryColor": site_content.get("primary_color"),
                "secondaryColor": site_content.get("secondary_color"),
                "font": site_content.get("font"),
            }
        ],
    }
    return GraphQLSiteConfigRepository(lambda: client)


class TestGraphQLSiteConfigRepository(SiteConfigRepositoryContract):
    def make_repository(self, site_content: dict[str, Any]) -> SiteConfigRepository:
        return _graphql_repository(site_content)


@pytest.fixture
def mock_client() -> Mock:
    return Mock(spec=Client)


@pytest.fixture
def repository(mock_client: Mock) -> GraphQLSiteConfigRepository:
    return GraphQLSiteConfigRepository(lambda: mock_client)


def _query_sent(mock_client: Mock) -> str:
    mock_client.execute.assert_called_once()
    return print_ast(mock_client.execute.call_args.args[0].document)


class TestGetSiteSettings:
    def test_reads_everything_in_one_request(
        self, repository: GraphQLSiteConfigRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {}

        repository.get_site_settings("pl")

        mock_client.execute.assert_called_once()

    def test_reads_published_localized_contents(
        self, repository: GraphQLSiteConfigRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {}

        repository.get_site_settings("pl")

        assert "localizedContents(stage: PUBLISHED" in _query_sent(mock_client)

    def test_default_entry_logo_wins_over_global_logo(
        self, repository: GraphQLSiteConfigRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {
            "localizedContents": [
                {"language": None, "logo": {"image": {"url": "/default.png"}}},
            ],
            "logos": [{"logo": {"image": {"url": "/global.png"}}}],
        }

        settings = repository.get_site_settings("en")

        assert settings == SiteSettings(logo=Image(url="/default.png"))

    def test_global_logo_is_used_without_a_default_entry(
        self, repository: GraphQLSiteConfigRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {
            "localizedContents": [],
            "logos": [{"logo": {"image": {"url": "/global.png"}}}],
        }

        settings = repository.get_site_settings("en")

        assert settings == SiteSettings(logo=Image(url="/global.png"))

    @pytest.mark.parametrize(
        "result",
        [
            {
                "localizedContents": [None, {"language": None, "logo": None}],
                "logos": [{"logo": None}],
                "favicons": [{"favicon": None}],
                "themes": [None],
            },
            {
                "localizedContents": [{"language": None, "logo": {"image": None}}],
                "logos": [{"logo": {"alternateText": "x", "image": None}}],
                "favicons": [None],
                "themes": [{"primaryColor": None, "secondaryColor": None, "font": None}],
            },
            {"localizedContents": None, "logos": None, "favicons": None, "themes": None},
        ],
    )
    def test_null_nodes_fall_back_to_defaults(
        self,
        repository: GraphQLSiteConfigRepository,
        mock_client: Mock,
        result: dict[str, Any],
    ):
        mock_client.execute.return_value = result

        assert repository.get_site_settings("en") == SiteSettings()
