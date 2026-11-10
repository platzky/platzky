"""Contract suite: every SiteConfigRepository behaves identically.

Parametrized over every backend that implements it (so far Json, Mongo) so the
independently-implemented repositories can't silently drift apart the way
from-scratch implementations of the same thing easily could. Each backend gets a
factory taking the same neutral `site_content` dict (the Json document's shape)
and translating it into what that backend stores: the Json document itself, or
a Mongo config document plus per-language menu and override documents.
How overrides fall back to the defaults is tested on `SiteSettings.from_layers`.
"""

from collections.abc import Mapping
from typing import Any, Callable
from unittest.mock import Mock

import pytest

from platzky.db.json_document import JsonDocument
from platzky.db.json_site_config_repository import JsonSiteConfigRepository
from platzky.db.json_stores import MemoryStore
from platzky.db.mongo_site_config_repository import MongoSiteConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository, SiteSettings
from platzky.models import Footer, Image, MenuItem, PageMeta

_SITE_CONTENT = {
    "logo_url": "/logo.png",
    "favicon_url": "/favicon.ico",
    "primary_color": "blue",
    "secondary_color": "green",
    "app_name": "Default name",
    "app_title": "Default title",
    "app_description": "Default description",
    "localized_content": {
        "pl": {
            "app_name": "Nazwa PL",
            "app_title": "Tytuł PL",
            "app_description": "Opis PL",
            "logo_url": "/logo-pl.png",
        }
    },
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


def _collection(documents: Mapping[str, Mapping[str, Any]]) -> Mock:
    def find_one(query: Mapping[str, str], **_: object) -> Mapping[str, Any] | None:
        return documents.get(query["_id"])

    return Mock(find_one=find_one)


def _mongo_repository(site_content: dict[str, Any]) -> SiteConfigRepository:
    # Mongo keeps the config in one document, and menus and overrides in one document
    # per language.
    config = {k: v for k, v in site_content.items() if k != "localized_content"}
    menu_items = site_content.get("menu_items") or {}
    localized_content = site_content.get("localized_content") or {}
    return MongoSiteConfigRepository(
        _collection({"config": config} if site_content else {}),
        _collection({lang: {"items": items} for lang, items in menu_items.items()}),
        _collection({lang: entry for lang, entry in localized_content.items()}),
    )


@pytest.fixture(
    params=[_json_repository, _mongo_repository],
    ids=["Json", "Mongo"],
)
def make_repository(
    request: pytest.FixtureRequest,
) -> Callable[[dict[str, Any]], SiteConfigRepository]:
    return request.param


class TestSiteConfigRepositoryContract:
    def test_get_site_settings_returns_non_localized_values(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        settings = make_repository(_SITE_CONTENT).get_site_settings("en")

        assert settings.logo is not None
        assert settings.logo.url == "/logo.png"
        assert settings.favicon_url == "/favicon.ico"
        assert settings.primary_color == "blue"
        assert settings.secondary_color == "green"

    def test_localized_content_wins_over_top_level(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        settings = make_repository(_SITE_CONTENT).get_site_settings("pl")

        assert settings == SiteSettings(
            logo=Image(url="/logo-pl.png"),
            favicon_url="/favicon.ico",
            primary_color="blue",
            secondary_color="green",
            app_name="Nazwa PL",
            app_title="Tytuł PL",
            app_description="Opis PL",
        )

    def test_language_without_entry_uses_top_level_values(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        settings = make_repository(_SITE_CONTENT).get_site_settings("de")

        assert settings.app_name == "Default name"
        assert settings.app_title == "Default title"
        assert settings.app_description == "Default description"
        assert settings.logo is not None
        assert settings.logo.url == "/logo.png"

    @pytest.mark.parametrize("localized_content", [None, {}, {"en": None}])
    def test_missing_or_null_localized_content_uses_top_level_values(
        self,
        make_repository: Callable[[dict[str, Any]], SiteConfigRepository],
        localized_content: dict[str, Any] | None,
    ):
        repository = make_repository({**_SITE_CONTENT, "localized_content": localized_content})

        settings = repository.get_site_settings("en")

        assert settings.app_name == "Default name"
        assert settings.app_description == "Default description"

    def test_get_site_settings_returns_defaults_when_empty(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        assert make_repository({}).get_site_settings("en") == SiteSettings()

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
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
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
