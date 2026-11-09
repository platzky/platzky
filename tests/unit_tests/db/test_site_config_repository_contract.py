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

_TEXT_KEYS = ["app_name", "app_title", "app_description"]

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
    menu_items = site_content.get("menu_items") or {}

    def find_menu(query: dict[str, Any]) -> dict[str, Any] | None:
        lang = query["_id"]
        return {"_id": lang, "items": menu_items[lang]} if lang in menu_items else None

    menu = Mock()
    menu.find_one.side_effect = find_menu

    # Mongo keeps per-language overrides as one document per language.
    config.find_one.return_value = (
        {"_id": "config", **{k: v for k, v in site_content.items() if k != "localized_content"}}
        if site_content
        else None
    )
    localized_content = site_content.get("localized_content") or {}

    def find_localized(query: dict[str, Any], projection: list[str]) -> dict[str, Any] | None:
        entry = localized_content.get(query["_id"])
        if entry is None:
            return None
        return {"_id": query["_id"], **{k: v for k, v in entry.items() if k in projection}}

    localized = Mock()
    localized.find_one.side_effect = find_localized
    return MongoSiteConfigRepository(config, menu, localized)


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

        assert settings.app_name == "Nazwa PL"
        assert settings.app_title == "Tytuł PL"
        assert settings.app_description == "Opis PL"

    def test_localized_logo_url_wins_over_top_level(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        settings = make_repository(_SITE_CONTENT).get_site_settings("pl")

        assert settings.logo is not None
        assert settings.logo.url == "/logo-pl.png"

    def test_language_without_entry_uses_top_level_values(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        settings = make_repository(_SITE_CONTENT).get_site_settings("de")

        assert settings.app_name == "Default name"
        assert settings.app_title == "Default title"
        assert settings.app_description == "Default description"
        assert settings.logo is not None
        assert settings.logo.url == "/logo.png"

    def test_key_missing_from_localized_entry_uses_top_level_value(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository(
            {**_SITE_CONTENT, "localized_content": {"en": {"app_name": "English name"}}}
        )

        settings = repository.get_site_settings("en")

        assert settings.app_name == "English name"
        assert settings.app_title == "Default title"

    @pytest.mark.parametrize("empty", [None, ""], ids=["null", "empty"])
    @pytest.mark.parametrize("key", _TEXT_KEYS)
    def test_empty_localized_value_falls_through_to_top_level(
        self,
        make_repository: Callable[[dict[str, Any]], SiteConfigRepository],
        key: str,
        empty: str | None,
    ):
        repository = make_repository({**_SITE_CONTENT, "localized_content": {"en": {key: empty}}})

        settings = repository.get_site_settings("en")

        assert getattr(settings, key) == _SITE_CONTENT[key]

    @pytest.mark.parametrize("empty", [None, ""], ids=["null", "empty"])
    def test_empty_localized_logo_url_falls_through_to_top_level(
        self,
        make_repository: Callable[[dict[str, Any]], SiteConfigRepository],
        empty: str | None,
    ):
        repository = make_repository(
            {**_SITE_CONTENT, "localized_content": {"en": {"logo_url": empty}}}
        )

        settings = repository.get_site_settings("en")

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
        settings = make_repository({}).get_site_settings("en")

        assert settings.logo is None
        assert settings.favicon_url == ""
        assert settings.primary_color == "white"
        assert settings.secondary_color == "navy"
        assert settings.font == ""
        assert settings.app_name == ""
        assert settings.app_title == ""
        assert settings.app_description == ""

    @pytest.mark.parametrize("key", _TEXT_KEYS)
    def test_explicit_null_top_level_text_is_treated_as_unconfigured(
        self,
        make_repository: Callable[[dict[str, Any]], SiteConfigRepository],
        key: str,
    ):
        settings = make_repository({key: None}).get_site_settings("en")

        assert getattr(settings, key) == ""

    def test_legacy_dict_app_description_resolves_by_language(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({"app_description": {"en": "Hello", "pl": "Cześć"}})

        assert repository.get_site_settings("en").app_description == "Hello"
        assert repository.get_site_settings("pl").app_description == "Cześć"

    def test_legacy_dict_app_description_is_empty_for_missing_language(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository({"app_description": {"en": "Hello"}})

        assert repository.get_site_settings("de").app_description == ""

    def test_localized_app_description_wins_over_legacy_dict(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        repository = make_repository(
            {
                "app_description": {"en": "Legacy"},
                "localized_content": {"en": {"app_description": "New"}},
            }
        )

        assert repository.get_site_settings("en").app_description == "New"

    def test_plain_top_level_logo_url_still_works(
        self, make_repository: Callable[[dict[str, Any]], SiteConfigRepository]
    ):
        settings = make_repository({"logo_url": "/only.png"}).get_site_settings("en")

        assert settings.logo is not None
        assert settings.logo.url == "/only.png"

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
