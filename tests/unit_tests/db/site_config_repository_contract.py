"""Contract suite every SiteConfigRepository backend must satisfy.

Subclass `SiteConfigRepositoryContract` in the backend's own test module (the class
name must start with `Test` there so pytest collects it) and override the
`make_repository` method. It takes a neutral `site_content` dict (the Json
document's shape: the site-wide keys plus ``localized_content``) and builds a
repository over whatever that backend stores. Inherited tests then run against that
backend, so independently-implemented repositories cannot silently drift apart.

A behaviour the backend cannot represent is opted out by overriding the test with
`@pytest.mark.skip(reason=...)`, which keeps the gap visible in the test report.
External database backends can reuse this module the same way.
How overrides fall back to the defaults is tested on `SiteSettings.from_layers`, and which
keys are valid on `SiteContent`, not here.

This module is not named `test_*`, and the class not `Test*`, so pytest only
collects the tests through the subclasses.
"""

from typing import Any

from platzky.db.site_config_repository import SiteConfigRepository, SiteSettings
from platzky.models import Font, Footer, Image, MenuItem, PageMeta

SITE_CONTENT = {
    "logo_url": "/logo.png",
    "favicon_url": "/favicon.ico",
    "primary_color": "blue",
    "secondary_color": "green",
    "font": {"name": "Lora", "url": "https://fonts.googleapis.com/css2?family=Lora"},
    "app_name": "Literature",
    "app_title": "Literature | Reading notes",
    "app_description": "Notes on Tolkien's books",
    "localized_content": {
        "en": {
            "blog_meta": {"title": "Reading notes", "description": "All the notes"},
            "footer": {"content": "English footer", "collapsible": True},
            "menu_items": [{"name": "Home", "url": "/"}, {"name": "Notes", "url": "/blog"}],
            "home_page_path": "/blog/page/about",
        },
        "pl": {
            "app_name": "Literatura",
            "app_title": "Literatura | Notatki z lektur",
            "app_description": "Notatki o książkach Tolkiena",
            "logo_url": "/logo-pl.png",
            "blog_meta": {"title": "Notatki", "description": "Wszystkie notatki"},
            "footer": {"content": "Stopka"},
            "menu_items": [{"name": "Start", "url": "/"}],
            "home_page_path": "/blog/page/o-nas",
        },
    },
}


class SiteConfigRepositoryContract:
    def make_repository(self, site_content: dict[str, Any]) -> SiteConfigRepository:
        """Build a repository of the backend under test holding this site content."""
        raise NotImplementedError("subclasses build a repository of their backend")

    def test_get_site_settings_returns_non_localized_values(self):
        settings = self.make_repository(SITE_CONTENT).get_site_settings("en")

        assert settings == SiteSettings(
            logo=Image(url="/logo.png"),
            favicon_url="/favicon.ico",
            font=Font(name="Lora", url="https://fonts.googleapis.com/css2?family=Lora"),
            primary_color="blue",
            secondary_color="green",
            app_name="Literature",
            app_title="Literature | Reading notes",
            app_description="Notes on Tolkien's books",
        )

    def test_localized_content_wins_over_top_level(self):
        settings = self.make_repository(SITE_CONTENT).get_site_settings("pl")

        assert settings == SiteSettings(
            logo=Image(url="/logo-pl.png"),
            favicon_url="/favicon.ico",
            font=Font(name="Lora", url="https://fonts.googleapis.com/css2?family=Lora"),
            primary_color="blue",
            secondary_color="green",
            app_name="Literatura",
            app_title="Literatura | Notatki z lektur",
            app_description="Notatki o książkach Tolkiena",
        )

    def test_get_site_settings_returns_defaults_when_empty(self):
        assert self.make_repository({}).get_site_settings("en") == SiteSettings()

    def test_get_menu_items_in_lang_returns_only_that_language(self):
        repository = self.make_repository(SITE_CONTENT)

        assert repository.get_menu_items_in_lang("en") == [
            MenuItem(name="Home", url="/"),
            MenuItem(name="Notes", url="/blog"),
        ]
        assert repository.get_menu_items_in_lang("pl") == [MenuItem(name="Start", url="/")]

    def test_get_menu_items_in_lang_returns_empty_list_for_unknown_language(self):
        assert self.make_repository(SITE_CONTENT).get_menu_items_in_lang("de") == []

    def test_get_menu_items_in_lang_returns_empty_list_when_unconfigured(self):
        assert self.make_repository({}).get_menu_items_in_lang("en") == []

    def test_get_home_page_path_returns_per_language_value(self):
        repository = self.make_repository(SITE_CONTENT)

        assert repository.get_home_page_path("en") == "/blog/page/about"
        assert repository.get_home_page_path("pl") == "/blog/page/o-nas"

    def test_get_home_page_path_returns_none_for_unconfigured_language(self):
        assert self.make_repository(SITE_CONTENT).get_home_page_path("de") is None

    def test_get_home_page_path_returns_none_when_unconfigured(self):
        assert self.make_repository({}).get_home_page_path("en") is None

    def test_get_footer_returns_footer_of_requested_language(self):
        repository = self.make_repository(SITE_CONTENT)

        assert repository.get_footer("en") == Footer(content="English footer", collapsible=True)
        assert repository.get_footer("pl") == Footer(content="Stopka", collapsible=False)

    def test_get_footer_is_empty_and_not_collapsible_when_unconfigured(self):
        assert self.make_repository({}).get_footer("en") == Footer(content="", collapsible=False)

    def test_get_footer_is_empty_for_unconfigured_language(self):
        assert self.make_repository(SITE_CONTENT).get_footer("de") == Footer()

    def test_get_blog_meta_returns_title_and_description_in_requested_language(self):
        repository = self.make_repository(SITE_CONTENT)

        assert repository.get_blog_meta("en") == PageMeta(
            title="Reading notes", description="All the notes"
        )
        assert repository.get_blog_meta("pl") == PageMeta(
            title="Notatki", description="Wszystkie notatki"
        )

    def test_get_blog_meta_is_empty_for_unconfigured_language(self):
        assert self.make_repository(SITE_CONTENT).get_blog_meta("de") == PageMeta()
