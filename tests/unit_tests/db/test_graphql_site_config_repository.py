"""GraphQL backend: the SiteConfigRepository contract plus the requests it sends."""

from collections.abc import Mapping
from typing import Any
from unittest.mock import Mock

import pytest
from gql import Client, GraphQLRequest
from graphql import print_ast

from platzky.db.graphql_site_config_repository import GraphQLSiteConfigRepository
from platzky.db.site_config_repository import (
    LocalizedContent,
    SiteConfigRepository,
    SiteContent,
)
from tests.unit_tests.db.site_config_repository_contract import SiteConfigRepositoryContract


def _hygraph_entry(content: Mapping[str, Any]) -> dict[str, Any]:
    """Map a neutral entry to what Hygraph answers for the aliased fields (nested logo)."""
    logo_url = content.get("logo_url")
    return {
        **{
            key: value
            for key, value in content.items()
            if key not in {"logo_url", "localized_content"}
        },
        "logo": {"image": {"url": logo_url}} if logo_url else None,
    }


class TestGraphQLSiteConfigRepository(SiteConfigRepositoryContract):
    def make_repository(self, site_content: dict[str, Any]) -> SiteConfigRepository:
        site_entry = _hygraph_entry(site_content)
        entries = {
            lang: _hygraph_entry(content)
            for lang, content in site_content.get("localized_content", {}).items()
        }
        client = Mock(spec=Client)

        def execute(
            _request: GraphQLRequest, variable_values: Mapping[str, str] | None = None
        ) -> dict[str, Any]:
            if variable_values is None:
                return {"sites": [site_entry]}
            return {"localizedContent": entries.get(variable_values["lang"])}

        client.execute.side_effect = execute
        return GraphQLSiteConfigRepository(lambda: client)


@pytest.fixture
def mock_client() -> Mock:
    return Mock(spec=Client)


@pytest.fixture
def repository(mock_client: Mock) -> GraphQLSiteConfigRepository:
    return GraphQLSiteConfigRepository(lambda: mock_client)


class TestRequests:
    def test_asks_the_server_for_the_language(
        self, repository: GraphQLSiteConfigRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {"localizedContent": None}

        repository.get_localized_content("pl")

        mock_client.execute.assert_called_once()
        assert "localizedContent(where: {language: $lang}" in print_ast(
            mock_client.execute.call_args.args[0].document
        )
        assert mock_client.execute.call_args.kwargs["variable_values"] == {"lang": "pl"}

    @pytest.mark.parametrize(
        "result",
        [
            {"sites": []},
            {"sites": [{"logo": None, "font": None}]},
            {
                "sites": [
                    {
                        "favicon_url": None,
                        "primary_color": None,
                        "secondary_color": None,
                        "font": {"name": None, "url": None},
                    }
                ]
            },
        ],
    )
    def test_null_site_nodes_fall_back_to_defaults(
        self,
        repository: GraphQLSiteConfigRepository,
        mock_client: Mock,
        result: dict[str, Any],
    ):
        mock_client.execute.return_value = result

        assert repository.get_site_content() == SiteContent()

    @pytest.mark.parametrize(
        "result",
        [
            {"localizedContent": None},
            {"localizedContent": {"logo": {"image": None}}},
            {
                "localizedContent": {
                    "blog_meta": None,
                    "footer": {"content": None, "collapsible": None},
                    "menu_items": [],
                }
            },
        ],
    )
    def test_null_localized_nodes_fall_back_to_defaults(
        self,
        repository: GraphQLSiteConfigRepository,
        mock_client: Mock,
        result: dict[str, Any],
    ):
        mock_client.execute.return_value = result

        assert repository.get_localized_content("en") == LocalizedContent()
