"""Contract suite every SiteConfigRepository backend must satisfy.

Subclass `SiteConfigRepositoryContract` in the backend's own test module (the class
name must start with `Test` there so pytest collects it) and override the
`make_repository` method. It takes a neutral `site_content` dict (the Json
document's shape) and builds a repository over whatever that backend stores.
Inherited tests then run against that backend, so independently-implemented
repositories cannot silently drift apart.

A behaviour the backend cannot represent is opted out by overriding the test with
`@pytest.mark.skip(reason=...)`, which keeps the gap visible in the test report.
External database backends can reuse this module the same way.
How overrides fall back to the defaults is tested on `SiteSettings.from_layers`.

This module is not named `test_*`, and the class not `Test*`, so pytest only
collects the tests through the subclasses.
"""

from typing import Any

import pytest

from platzky.db.site_config_repository import SiteConfigRepository, SiteSettings
from platzky.models import Footer, Image, MenuItem, PageMeta

SITE_CONTENT = {
    "logo_url": "/logo.png",
    "favicon_url": "/favicon.ico",
    "primary_color": "blue",
    "secondary_color": "green",
    "font": "Arial",
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

MENU_ITEMS = {
    "en": [{"name": "Home", "url": "/"}, {"name": "Blog", "url": "/blog"}],
    "pl": [{"name": "Start", "url": "/"}],
}
FOOTER = {"content": {"en": "English footer", "pl": "Stopka"}, "collapsible": True}
BLOG_META = {
    "en": {"title": "Blog", "description": "All posts"},
    "pl": {"title": "Blog PL", "description": "Wszystkie wpisy"},
}


class SiteConfigRepositoryContract:
    def make_repository(self, site_content: dict[str, Any]) -> SiteConfigRepository:
        """Build a repository of the backend under test holding this site content."""
        raise NotImplementedError("subclasses build a repository of their backend")

    def test_get_site_settings_returns_non_localized_values(self):
        settings = self.make_repository(SITE_CONTENT).get_site_settings("en")

        assert settings.logo is not None
        assert settings.logo.url == "/logo.png"
        assert settings.favicon_url == "/favicon.ico"
        assert settings.font == "Arial"
        assert settings.primary_color == "blue"
        assert settings.secondary_color == "green"

    def test_localized_content_wins_over_top_level(self):
        settings = self.make_repository(SITE_CONTENT).get_site_settings("pl")

        assert settings == SiteSettings(
            logo=Image(url="/logo-pl.png"),
            favicon_url="/favicon.ico",
            font="Arial",
            primary_color="blue",
            secondary_color="green",
            app_name="Nazwa PL",
            app_title="Tytuł PL",
            app_description="Opis PL",
        )

    def test_language_without_entry_uses_top_level_values(self):
        settings = self.make_repository(SITE_CONTENT).get_site_settings("de")

        assert settings.app_name == "Default name"
        assert settings.app_title == "Default title"
        assert settings.app_description == "Default description"
        assert settings.logo is not None
        assert settings.logo.url == "/logo.png"

    @pytest.mark.parametrize("localized_content", [None, {}, {"en": None}])
    def test_missing_or_null_localized_content_uses_top_level_values(
        self, localized_content: dict[str, Any] | None
    ):
        repository = self.make_repository({**SITE_CONTENT, "localized_content": localized_content})

        settings = repository.get_site_settings("en")

        assert settings.app_name == "Default name"
        assert settings.app_description == "Default description"

    def test_null_top_level_values_fall_back_to_defaults(self):
        repository = self.make_repository(
            {
                "logo_url": None,
                "favicon_url": None,
                "primary_color": None,
                "secondary_color": None,
                "font": None,
                "app_description": None,
            }
        )

        assert repository.get_site_settings("en") == SiteSettings()

    def test_get_site_settings_returns_defaults_when_empty(self):
        assert self.make_repository({}).get_site_settings("en") == SiteSettings()

    @pytest.mark.parametrize(
        "site_content",
        [
            {"menu_items": None, "blog_meta": None, "footer": None},
            {"menu_items": {"en": None}, "blog_meta": {"en": None}, "footer": {"content": None}},
        ],
        ids=["null-sections", "null-entries"],
    )
    def test_explicit_nulls_are_treated_as_unconfigured(self, site_content: dict[str, Any]):
        repository = self.make_repository(site_content)

        assert repository.get_menu_items_in_lang("en") == []
        assert repository.get_blog_meta("en") == PageMeta()
        assert repository.get_footer("en") == Footer()

    def test_get_menu_items_in_lang_returns_only_that_language(self):
        repository = self.make_repository({"menu_items": MENU_ITEMS})

        assert repository.get_menu_items_in_lang("en") == [
            MenuItem(name="Home", url="/"),
            MenuItem(name="Blog", url="/blog"),
        ]
        assert repository.get_menu_items_in_lang("pl") == [MenuItem(name="Start", url="/")]

    def test_get_menu_items_in_lang_returns_empty_list_for_unknown_language(self):
        repository = self.make_repository({"menu_items": MENU_ITEMS})

        assert repository.get_menu_items_in_lang("de") == []

    def test_get_menu_items_in_lang_returns_empty_list_when_unconfigured(self):
        repository = self.make_repository({})

        assert repository.get_menu_items_in_lang("en") == []

    def test_get_home_page_path_returns_plain_string_for_any_locale(self):
        repository = self.make_repository({"home_page_path": "/welcome"})

        assert repository.get_home_page_path("en") == "/welcome"

    def test_get_home_page_path_returns_per_locale_value(self):
        repository = self.make_repository({"home_page_path": {"en": "/home", "pl": "/start"}})

        assert repository.get_home_page_path("en") == "/home"
        assert repository.get_home_page_path("pl") == "/start"

    def test_get_home_page_path_falls_back_to_default_key(self):
        repository = self.make_repository(
            {"home_page_path": {"en": "/home", "default": "/fallback"}}
        )

        assert repository.get_home_page_path("en") == "/home"
        assert repository.get_home_page_path("de") == "/fallback"

    def test_get_home_page_path_returns_none_for_unlisted_locale_without_default(self):
        repository = self.make_repository({"home_page_path": {"en": "/home"}})

        assert repository.get_home_page_path("de") is None

    def test_get_home_page_path_returns_none_when_unconfigured(self):
        repository = self.make_repository({})

        assert repository.get_home_page_path("en") is None

    def test_get_footer_returns_content_in_requested_language(self):
        repository = self.make_repository({"footer": FOOTER})

        assert repository.get_footer("en") == Footer(content="English footer", collapsible=True)
        assert repository.get_footer("pl") == Footer(content="Stopka", collapsible=True)

    def test_get_footer_is_empty_and_not_collapsible_when_unconfigured(self):
        repository = self.make_repository({})

        assert repository.get_footer("en") == Footer(content="", collapsible=False)

    def test_get_blog_meta_returns_title_and_description_in_requested_language(self):
        repository = self.make_repository({"blog_meta": BLOG_META})

        assert repository.get_blog_meta("en") == PageMeta(title="Blog", description="All posts")
        assert repository.get_blog_meta("pl") == PageMeta(
            title="Blog PL", description="Wszystkie wpisy"
        )

    def test_get_blog_meta_is_empty_for_unconfigured_language(self):
        repository = self.make_repository({"blog_meta": BLOG_META})

        assert repository.get_blog_meta("de") == PageMeta()

    def test_get_footer_is_empty_for_unconfigured_language(self):
        repository = self.make_repository({"footer": {"content": {"en": "English footer"}}})

        assert repository.get_footer("de") == Footer()
