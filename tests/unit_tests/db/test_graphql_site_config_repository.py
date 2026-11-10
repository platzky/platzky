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


def _for_language(site_content: Mapping[str, Any], field: str, lang: str) -> object:
    return (site_content.get(field) or {}).get(lang)


def _hygraph_default_entry(site_content: Mapping[str, Any]) -> dict[str, Any]:
    logo_url = site_content.get("logo_url")
    return {
        "language": None,
        "appName": site_content.get("app_name"),
        "appTitle": site_content.get("app_title"),
        "appDescription": site_content.get("app_description"),
        "logo": {"image": {"url": logo_url}} if logo_url else None,
    }


def _hygraph_language_entry(site_content: Mapping[str, Any], lang: str) -> dict[str, Any]:
    localized = (site_content.get("localized_content") or {}).get(lang) or {}
    footer = site_content.get("footer") or {}
    logo_url = localized.get("logo_url")
    return {
        "language": lang,
        "appName": localized.get("app_name"),
        "appTitle": localized.get("app_title"),
        "appDescription": localized.get("app_description"),
        "logo": {"image": {"url": logo_url}} if logo_url else None,
        "blogMeta": _for_language(site_content, "blog_meta", lang),
        "footer": {
            "content": (footer.get("content") or {}).get(lang),
            "collapsible": footer.get("collapsible"),
        },
        "homePagePath": _for_language(site_content, "home_page_path", lang),
        "menuItems": _for_language(site_content, "menu_items", lang),
    }


def _graphql_repository(site_content: dict[str, Any]) -> SiteConfigRepository:
    languages = {
        lang
        for field in ("localized_content", "menu_items", "blog_meta", "home_page_path")
        for lang in site_content.get(field) or {}
    } | set((site_content.get("footer") or {}).get("content") or {})
    entries = [_hygraph_default_entry(site_content)] + [
        _hygraph_language_entry(site_content, lang) for lang in languages
    ]
    client = Mock(spec=Client)
    client.execute.return_value = {
        "localizedContents": entries,
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

    @pytest.mark.skip(reason="a single home page path for every locale has no Hygraph equivalent")
    def test_get_home_page_path_returns_plain_string_for_any_locale(self):
        raise NotImplementedError

    @pytest.mark.skip(reason="the default home page path key has no Hygraph equivalent")
    def test_get_home_page_path_falls_back_to_default_key(self):
        raise NotImplementedError


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
