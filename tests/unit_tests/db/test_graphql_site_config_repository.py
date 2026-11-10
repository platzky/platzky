"""GraphQL backend: the SiteConfigRepository contract plus the requests it sends."""

from collections.abc import Mapping
from typing import Any
from unittest.mock import Mock

import pytest
from gql import Client, GraphQLRequest
from graphql import print_ast

from platzky.db.graphql_site_config_repository import GraphQLSiteConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository, SiteSettings
from tests.unit_tests.db.site_config_repository_contract import SiteConfigRepositoryContract


def _hygraph_entry(content: Mapping[str, Any]) -> dict[str, Any]:
    """Map a neutral entry to a Hygraph entry (camelCase, nested logo)."""
    logo_url = content.get("logo_url")
    return {
        "appName": content.get("app_name"),
        "appTitle": content.get("app_title"),
        "appDescription": content.get("app_description"),
        "logo": {"image": {"url": logo_url}} if logo_url else None,
        "faviconUrl": content.get("favicon_url"),
        "primaryColor": content.get("primary_color"),
        "secondaryColor": content.get("secondary_color"),
        "font": content.get("font"),
        "blogMeta": content.get("blog_meta"),
        "footer": content.get("footer"),
        "homePagePath": content.get("home_page_path"),
        "menuItems": content.get("menu_items", []),
    }


class TestGraphQLSiteConfigRepository(SiteConfigRepositoryContract):
    def make_repository(self, site_content: dict[str, Any]) -> SiteConfigRepository:
        site_entry = _hygraph_entry(site_content)
        entries = {
            lang: _hygraph_entry(content)
            for lang, content in site_content.get("localized_content", {}).items()
        }
        client = Mock(spec=Client)

        def execute(_query: GraphQLRequest, variable_values: Mapping[str, str]) -> dict[str, Any]:
            return {"site": [site_entry], "localized": entries.get(variable_values["lang"])}

        client.execute.side_effect = execute
        return GraphQLSiteConfigRepository(lambda: client)


@pytest.fixture
def mock_client() -> Mock:
    return Mock(spec=Client)


@pytest.fixture
def repository(mock_client: Mock) -> GraphQLSiteConfigRepository:
    return GraphQLSiteConfigRepository(lambda: mock_client)


class TestGetSiteSettings:
    def test_asks_the_server_for_the_language(
        self, repository: GraphQLSiteConfigRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {"site": [], "localized": None}

        repository.get_site_settings("pl")

        mock_client.execute.assert_called_once()
        assert "localizedContent(where: {language: $lang}" in print_ast(
            mock_client.execute.call_args.args[0].document
        )
        assert mock_client.execute.call_args.kwargs["variable_values"] == {"lang": "pl"}

    @pytest.mark.parametrize(
        "result",
        [
            {"site": [], "localized": None},
            {"site": [{"logo": None, "font": None}], "localized": {"logo": {"image": None}}},
            {
                "site": [
                    {
                        "faviconUrl": None,
                        "primaryColor": None,
                        "secondaryColor": None,
                        "font": None,
                    }
                ],
                "localized": {"blogMeta": None, "footer": None, "menuItems": []},
            },
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
