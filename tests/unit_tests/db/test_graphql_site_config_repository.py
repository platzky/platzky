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
    SiteConfig,
    SiteConfigRepository,
)
from platzky.models import Footer
from tests.unit_tests.db.site_config_repository_contract import SiteConfigRepositoryContract

_NO_LANGUAGE = {"lang": None}


SCHEMA_REASON = "Hygraph's schema cannot store this: the server never returns such data"


class TestGraphQLSiteConfigRepository(SiteConfigRepositoryContract):
    def make_repository(self, site_config: dict[str, Any]) -> SiteConfigRepository:
        # With snake_case aliases, Hygraph answers in the neutral shape itself.
        site_entry = {k: v for k, v in site_config.items() if k != "localized_content"}
        entries = site_config.get("localized_content", {})
        client = Mock(spec=Client)

        def execute(
            _request: GraphQLRequest, variable_values: Mapping[str, str | None] = _NO_LANGUAGE
        ) -> dict[str, Any]:
            return {"sites": [site_entry], "localizedContent": entries.get(variable_values["lang"])}

        client.execute.side_effect = execute
        return GraphQLSiteConfigRepository(lambda: client)

    @pytest.mark.skip(reason=SCHEMA_REASON)
    def test_invalid_site_wide_value_is_an_invalid_data_error(self):
        pass

    @pytest.mark.skip(reason=SCHEMA_REASON)
    def test_null_text_in_a_language_is_an_invalid_data_error(self):
        pass

    @pytest.mark.skip(reason=SCHEMA_REASON)
    def test_unknown_key_in_a_language_is_an_invalid_data_error(self):
        pass


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
            {"sites": [], "localizedContent": None},
            {
                "sites": [{"logo_url": None, "font": None}],
                "localizedContent": {"logo_url": None},
            },
            {
                "sites": [
                    {
                        "favicon_url": None,
                        "primary_color": None,
                        "secondary_color": None,
                        "font": {"name": None, "url": None},
                    }
                ],
                "localizedContent": {
                    "footer": {"content": None, "collapsible": None},
                    "menu_items": [],
                },
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

        assert repository.get_site_config() == SiteConfig()
        assert repository.get_localized_content("en") == LocalizedContent()

    def test_false_and_zero_values_are_kept(
        self, repository: GraphQLSiteConfigRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {
            "localizedContent": {"footer": {"content": "Footer", "collapsible": False}}
        }

        assert repository.get_localized_content("en") == LocalizedContent(
            footer=Footer(content="Footer")
        )
