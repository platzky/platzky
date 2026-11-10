from typing import Any
from unittest.mock import Mock

import pytest
from gql import Client
from graphql import print_ast

from platzky.db.graphql_site_config_repository import GraphQLSiteConfigRepository
from platzky.db.site_config_repository import SiteSettings
from platzky.models import Image


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

    def test_global_logo_and_font_are_used_without_a_default_entry(
        self, repository: GraphQLSiteConfigRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {
            "localizedContents": [],
            "logos": [{"logo": {"image": {"url": "/global.png"}}}],
            "themes": [{"primaryColor": "red", "secondaryColor": "blue", "font": "Lato"}],
        }

        settings = repository.get_site_settings("en")

        assert settings == SiteSettings(
            logo=Image(url="/global.png"), primary_color="red", secondary_color="blue", font="Lato"
        )

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
