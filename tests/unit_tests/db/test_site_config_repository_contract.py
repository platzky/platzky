"""Contract suite: every SiteConfigRepository behaves identically.

Parametrized over every backend that implements it (so far Json, Mongo) so the
independently-implemented repositories can't silently drift apart the way
from-scratch implementations of the same thing easily could. Each backend gets a
factory taking the same neutral `site_content` dict (the Json document's shape)
and translating it into what that backend stores: the Json document itself, or
a Mongo config document plus a per-language menu collection.
"""

from typing import Any, Callable
from unittest.mock import Mock

import pytest

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
    menu_items = site_content.get("menu_items") or {}

    def find_menu(query: dict[str, Any]) -> dict[str, Any] | None:
        lang = query["_id"]
        return {"_id": lang, "items": menu_items[lang]} if lang in menu_items else None

    menu = Mock()
    menu.find_one.side_effect = find_menu
    return MongoSiteConfigRepository(config, menu)


@pytest.fixture(
    params=[_json_repository, _mongo_repository],
    ids=["Json", "Mongo"],
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

    @pytest.mark.parametrize(
        "site_content",
        [
            {"menu_items": None, "blog_meta": None, "footer": None},
            {"menu_items": {"en": None}, "blog_meta": {"en": None}, "footer": {"content": None}},
        ],
        ids=["null-sections", "null-entries"],
    )
    def test_explicit_nulls_are_treated_as_unconfigured(
        self,
        make_repository: Callable[[dict[str, Any]], SiteConfigRepository],
        site_content: dict[str, Any],
    ):
        repository = make_repository(site_content)

        assert repository.get_menu_items_in_lang("en") == []
        assert repository.get_blog_meta("en") == PageMeta()
        assert repository.get_footer("en") == Footer()

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

    def test_get_footer_returns_content_in_requested_language(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({"footer": _FOOTER})

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

        assert repository.get_blog_meta("en") == PageMeta(title="Blog", description="All posts")
        assert repository.get_blog_meta("pl") == PageMeta(
            title="Blog PL", description="Wszystkie wpisy"
        )

    def test_get_blog_meta_is_empty_for_unconfigured_language(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({"blog_meta": _BLOG_META})

        assert repository.get_blog_meta("de") == PageMeta()
