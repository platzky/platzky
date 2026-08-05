"""Contract suite: every SiteConfigRepository's get_site_settings() behaves
identically.

Parametrized over the three backends (Json, Mongo, GraphQL) so the newly
introduced, independently-implemented `get_site_settings()` can't silently
drift apart the way three from-scratch implementations of the same thing
easily could. `font` is intentionally not asserted here: GraphQL has never
implemented it (returns "" unconditionally, a pre-existing, documented
limitation) -- that's covered per-backend in each repository's own test file.
"""

from typing import Any, Callable
from unittest.mock import Mock, patch

import pytest

from platzky.db.graphql_site_config_repository import GraphQLSiteConfigRepository
from platzky.db.json_site_config_repository import JsonSiteConfigRepository
from platzky.db.mongo_site_config_repository import MongoSiteConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository

_SITE_CONTENT = {
    "logo_url": "/logo.png",
    "favicon_url": "/favicon.ico",
    "primary_color": "blue",
    "secondary_color": "green",
    "app_description": {"en": "Hello", "pl": "Cześć"},
}


def _json_repository(site_content: dict[str, Any]) -> SiteConfigRepository:
    return JsonSiteConfigRepository({"site_content": site_content})


def _mongo_repository(site_content: dict[str, Any]) -> SiteConfigRepository:
    collection = Mock()
    collection.find_one.return_value = {"_id": "config", **site_content} if site_content else None
    return MongoSiteConfigRepository(collection, Mock())


def _graphql_repository(site_content: dict[str, Any]) -> SiteConfigRepository:
    with patch("platzky.db.graphql_client.Client") as mock_client_class:
        mock_client = Mock()
        if site_content:
            mock_client.execute.return_value = {
                "logos": [
                    {"logo": {"alternateText": "", "image": {"url": site_content["logo_url"]}}}
                ],
                "favicons": [{"favicon": {"url": site_content["favicon_url"]}}],
                "themes": [
                    {
                        "primaryColor": site_content["primary_color"],
                        "secondaryColor": site_content["secondary_color"],
                    }
                ],
                "applicationSetups": [
                    {"language": lang, "applicationDescription": desc}
                    for lang, desc in site_content.get("app_description", {}).items()
                ],
            }
        else:
            mock_client.execute.return_value = {
                "logos": [],
                "favicons": [],
                "themes": [],
                "applicationSetups": [],
            }
        mock_client_class.return_value = mock_client
        repository = GraphQLSiteConfigRepository("https://test.endpoint", "test_token")
        # Call the public get_site_settings() once, while Client is still
        # patched, so the lazily-built client is constructed (and cached) now
        # rather than on the caller's later, unpatched call.
        repository.get_site_settings()
    return repository


@pytest.fixture(
    params=[_json_repository, _mongo_repository, _graphql_repository],
    ids=["Json", "Mongo", "GraphQL"],
)
def make_repository(
    request: pytest.FixtureRequest,
) -> Callable[[dict[str, Any]], SiteConfigRepository]:
    return request.param


class TestSiteConfigRepositoryContract:
    def test_get_site_settings_returns_configured_values(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository(_SITE_CONTENT)

        settings = repository.get_site_settings()

        assert settings.logo is not None
        assert settings.logo.url == "/logo.png"
        assert settings.favicon_url == "/favicon.ico"
        assert settings.primary_color == "blue"
        assert settings.secondary_color == "green"
        assert settings.app_description == {"en": "Hello", "pl": "Cześć"}

    def test_get_site_settings_returns_defaults_when_empty(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({})

        settings = repository.get_site_settings()

        assert settings.logo is None
        assert settings.favicon_url == ""
        assert settings.primary_color == "white"
        assert settings.secondary_color == "navy"
        assert settings.app_description == {}
