"""Contract suite: every SiteConfigRepository behaves identically.

Parametrized over the three backends (Json, Mongo, GraphQL) so the
independently-implemented repositories can't silently drift apart the way three
from-scratch implementations of the same thing easily could. Each backend gets a
factory taking the same neutral `site_content` dict (the Json document's shape)
and translating it into what that backend stores: the Json document itself, a
Mongo config document plus a per-language menu collection, or a fake GraphQL
client answering each query the repository sends.

Known, documented backend limitations are encoded as explicit per-backend
expectations rather than skipped: `font` is not asserted here (GraphQL has never
implemented it and returns "" -- covered in that repository's own test file);
GraphQL returns an empty `Footer()` / `PageMeta()` (it has no such CMS models);
and GraphQL has no "default" homepage fallback (strict xfail below).
"""

from typing import Any, Callable
from unittest.mock import Mock

import pytest
from gql import Client, GraphQLRequest
from graphql import print_ast

from platzky.db.graphql_site_config_repository import GraphQLSiteConfigRepository
from platzky.db.json_document import JsonDocument
from platzky.db.json_site_config_repository import JsonSiteConfigRepository
from platzky.db.json_stores import MemoryStore
from platzky.db.mongo_site_config_repository import MongoSiteConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository
from platzky.models import Footer, MenuItem, PageMeta

_SITE_CONTENT = {
    "logo_url": "/logo.png",
    "favicon_url": "/favicon.ico",
    "primary_color": "blue",
    "secondary_color": "green",
    "app_description": {"en": "Hello", "pl": "Cześć"},
}

_MENU_ITEMS = {
    "en": [{"name": "Home", "url": "/"}, {"name": "Blog", "url": "/blog"}],
    "pl": [{"name": "Start", "url": "/"}],
}
_FOOTER = {"content": {"en": "English footer", "pl": "Stopka"}, "collapsible": True}
_BLOG_META = {
    "en": {"title": "Blog", "description": "All posts"},
    "pl": {"title": "Blog PL", "description": "Wszystkie wpisy"},
}


def _json_repository(site_content: dict[str, Any]) -> SiteConfigRepository:
    return JsonSiteConfigRepository(JsonDocument(MemoryStore({"site_content": site_content})))


def _mongo_repository(site_content: dict[str, Any]) -> SiteConfigRepository:
    config = Mock()
    config.find_one.return_value = {"_id": "config", **site_content} if site_content else None
    menu_items = site_content.get("menu_items", {})

    def find_menu(query: dict[str, Any]) -> dict[str, Any] | None:
        lang = query["_id"]
        return {"_id": lang, "items": menu_items[lang]} if lang in menu_items else None

    menu = Mock()
    menu.find_one.side_effect = find_menu
    return MongoSiteConfigRepository(config, menu)


def _graphql_repository(site_content: dict[str, Any]) -> SiteConfigRepository:
    def execute(
        query: GraphQLRequest, variable_values: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        variables = variable_values or {}
        lang = variables.get("lang")
        operation = print_ast(query.document)
        if "menuItems" in operation:
            return {"menuItems": site_content.get("menu_items", {}).get(lang, [])}
        if "homePagePath" in operation:
            # One applicationSetups entry per language; no "default" concept.
            home = site_content.get("home_page_path")
            if isinstance(home, dict):
                home = home.get(lang)
            return {"applicationSetups": [{"homePagePath": home}] if home is not None else []}
        return {
            "logos": (
                [{"logo": {"alternateText": "", "image": {"url": site_content["logo_url"]}}}]
                if "logo_url" in site_content
                else []
            ),
            "favicons": (
                [{"favicon": {"url": site_content["favicon_url"]}}]
                if "favicon_url" in site_content
                else []
            ),
            "themes": (
                [
                    {
                        "primaryColor": site_content["primary_color"],
                        "secondaryColor": site_content["secondary_color"],
                    }
                ]
                if "primary_color" in site_content
                else []
            ),
            "applicationSetups": [
                {"language": language, "applicationDescription": desc}
                for language, desc in site_content.get("app_description", {}).items()
            ],
        }

    mock_client = Mock(spec=Client)
    mock_client.execute.side_effect = execute
    return GraphQLSiteConfigRepository(lambda: mock_client)


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

    def test_get_menu_items_in_lang_returns_only_that_language(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({"menu_items": _MENU_ITEMS})

        assert repository.get_menu_items_in_lang("en") == [
            MenuItem(name="Home", url="/"),
            MenuItem(name="Blog", url="/blog"),
        ]
        assert repository.get_menu_items_in_lang("pl") == [MenuItem(name="Start", url="/")]

    def test_get_menu_items_in_lang_returns_empty_list_for_unknown_language(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({"menu_items": _MENU_ITEMS})

        assert repository.get_menu_items_in_lang("de") == []

    def test_get_menu_items_in_lang_returns_empty_list_when_unconfigured(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({})

        assert repository.get_menu_items_in_lang("en") == []

    def test_get_home_page_path_returns_plain_string_for_any_locale(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({"home_page_path": "/welcome"})

        assert repository.get_home_page_path("en") == "/welcome"

    def test_get_home_page_path_returns_per_locale_value(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({"home_page_path": {"en": "/home", "pl": "/start"}})

        assert repository.get_home_page_path("en") == "/home"
        assert repository.get_home_page_path("pl") == "/start"

    def test_get_home_page_path_falls_back_to_default_key(
        self,
        request: pytest.FixtureRequest,
        make_repository: Callable[[dict[str, Any]], SiteConfigRepository],
    ):
        if make_repository is _graphql_repository:
            request.applymarker(
                pytest.mark.xfail(
                    strict=True,
                    reason=(
                        "GraphQL keeps one homePagePath per language entry and has no "
                        "'default' fallback: an unlisted locale resolves to None"
                    ),
                )
            )
        repository = make_repository({"home_page_path": {"en": "/home", "default": "/fallback"}})

        assert repository.get_home_page_path("en") == "/home"
        assert repository.get_home_page_path("de") == "/fallback"

    def test_get_home_page_path_returns_none_for_unlisted_locale_without_default(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({"home_page_path": {"en": "/home"}})

        assert repository.get_home_page_path("de") is None

    def test_get_home_page_path_returns_none_when_unconfigured(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({})

        assert repository.get_home_page_path("en") is None

    def test_get_footer_returns_content_in_requested_language(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({"footer": _FOOTER})

        if make_repository is _graphql_repository:
            # GraphQL has no footer model: documented to always return an empty Footer.
            assert repository.get_footer("en") == Footer()
            return
        assert repository.get_footer("en") == Footer(content="English footer", collapsible=True)
        assert repository.get_footer("pl") == Footer(content="Stopka", collapsible=True)

    def test_get_footer_is_empty_and_not_collapsible_when_unconfigured(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({})

        assert repository.get_footer("en") == Footer(content="", collapsible=False)

    def test_get_blog_meta_returns_title_and_description_in_requested_language(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({"blog_meta": _BLOG_META})

        if make_repository is _graphql_repository:
            # GraphQL has no blog meta model: documented to always return an empty PageMeta.
            assert repository.get_blog_meta("en") == PageMeta()
            return
        assert repository.get_blog_meta("en") == PageMeta(title="Blog", description="All posts")
        assert repository.get_blog_meta("pl") == PageMeta(
            title="Blog PL", description="Wszystkie wpisy"
        )

    def test_get_blog_meta_is_empty_for_unconfigured_language(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({"blog_meta": _BLOG_META})

        assert repository.get_blog_meta("de") == PageMeta()
