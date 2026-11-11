"""Contract suite every SiteConfigRepository backend must satisfy.

Subclass `SiteConfigRepositoryContract` in the backend's own test module (the class
name must start with `Test` there so pytest collects it) and override the
`make_repository` method. It takes a neutral `site_config` dict (the Json
document's shape: the site-wide keys plus ``localized_content``) and builds a
repository over whatever that backend stores. Inherited tests then run against that
backend, so independently-implemented repositories cannot silently drift apart.

A backend that stores arbitrary data (a JSON document, Mongo documents) must also reject
invalid data: subclass `StoredSiteConfigContract` instead. A backend whose storage enforces
its own schema (Hygraph) cannot hold such data, so it subclasses only the base contract.
External database backends can reuse this module the same way.
Each backend only has to map its stored content to `SiteConfig` and `LocalizedContent`.
How overrides fall back to the defaults is tested on `SiteSettings.from_layers`, and which
keys are valid on the models, not here.

This module is not named `test_*`, and the class not `Test*`, so pytest only
collects the tests through the subclasses.
"""

from abc import ABC, abstractmethod
from typing import Any

import pytest

from platzky.db.exceptions import InvalidDataError
from platzky.db.site_config_repository import (
    LocalizedContent,
    SiteConfig,
    SiteConfigRepository,
)
from platzky.models import Font, Footer, MenuItem

SITE_CONFIG = {
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
            "footer": {"content": "English footer", "collapsible": True},
            "menu_items": [{"name": "Home", "url": "/"}, {"name": "Notes", "url": "/blog"}],
            "home_page_path": "/blog/page/about",
        },
        "pl": {
            "app_name": "Literatura",
            "app_title": "Literatura | Notatki z lektur",
            "app_description": "Notatki o książkach Tolkiena",
            "logo_url": "/logo-pl.png",
            "footer": {"content": "Stopka"},
            "menu_items": [{"name": "Start", "url": "/"}],
            "home_page_path": "/blog/page/o-nas",
        },
    },
}


class SiteConfigRepositoryContract(ABC):
    @abstractmethod
    def make_repository(self, site_config: dict[str, Any]) -> SiteConfigRepository:
        """Build a repository of the backend under test holding this site config."""

    def test_get_site_config_returns_the_site_wide_values(self):
        assert self.make_repository(SITE_CONFIG).get_site_config() == SiteConfig(
            app_name="Literature",
            app_title="Literature | Reading notes",
            app_description="Notes on Tolkien's books",
            logo_url="/logo.png",
            favicon_url="/favicon.ico",
            font=Font(name="Lora", url="https://fonts.googleapis.com/css2?family=Lora"),
            primary_color="blue",
            secondary_color="green",
        )

    def test_get_site_config_returns_defaults_when_empty(self):
        assert self.make_repository({}).get_site_config() == SiteConfig()

    def test_get_localized_content_returns_the_entry_of_the_language(self):
        repository = self.make_repository(SITE_CONFIG)

        assert repository.get_localized_content("en") == LocalizedContent(
            footer=Footer(content="English footer", collapsible=True),
            menu_items=(MenuItem(name="Home", url="/"), MenuItem(name="Notes", url="/blog")),
            home_page_path="/blog/page/about",
        )
        assert repository.get_localized_content("pl") == LocalizedContent(
            app_name="Literatura",
            app_title="Literatura | Notatki z lektur",
            app_description="Notatki o książkach Tolkiena",
            logo_url="/logo-pl.png",
            footer=Footer(content="Stopka"),
            menu_items=(MenuItem(name="Start", url="/"),),
            home_page_path="/blog/page/o-nas",
        )

    def test_get_localized_content_is_empty_for_unknown_language(self):
        assert self.make_repository(SITE_CONFIG).get_localized_content("de") == LocalizedContent()


class StoredSiteConfigContract(SiteConfigRepositoryContract):
    """The contract plus rejecting invalid stored data, for backends that store any data.

    A backend may reject invalid data when it is built or when it is read.
    """

    def test_invalid_site_wide_value_is_an_invalid_data_error(self):
        with pytest.raises(InvalidDataError, match=r"site_config\.primary_color"):
            self.make_repository({"primary_color": ""}).get_site_config()

    def test_null_text_in_a_language_is_an_invalid_data_error(self):
        with pytest.raises(InvalidDataError, match=r"localized_content\.en\.app_name"):
            self.make_repository(
                {"localized_content": {"en": {"app_name": None}}}
            ).get_localized_content("en")

    def test_unknown_key_in_a_language_is_an_invalid_data_error(self):
        with pytest.raises(InvalidDataError, match=r"localized_content\.en\.unknown"):
            self.make_repository(
                {"localized_content": {"en": {"unknown": 1}}}
            ).get_localized_content("en")
