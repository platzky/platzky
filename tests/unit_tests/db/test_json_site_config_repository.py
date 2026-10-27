from typing import Any

from platzky.db.json_document import JsonDocument
from platzky.db.json_site_config_repository import JsonSiteConfigRepository
from platzky.db.json_stores import MemoryStore
from platzky.db.site_config_repository import SiteSettings
from platzky.models import Footer, PageMeta


def _repository(data: dict[str, Any]) -> JsonSiteConfigRepository:
    return JsonSiteConfigRepository(JsonDocument(MemoryStore(data)))


class TestJsonSiteConfigRepository:
    def test_get_site_settings(self):
        repository = _repository(
            {
                "site_content": {
                    "logo_url": "/logo.png",
                    "favicon_url": "/favicon.ico",
                    "font": "Arial",
                    "primary_color": "blue",
                    "secondary_color": "green",
                    "app_description": {"en": "Hello", "pl": "Cześć"},
                }
            }
        )

        settings = repository.get_site_settings()

        assert settings.logo is not None
        assert settings.logo.url == "/logo.png"
        assert settings.favicon_url == "/favicon.ico"
        assert settings.font == "Arial"
        assert settings.primary_color == "blue"
        assert settings.secondary_color == "green"
        assert settings.app_description == {"en": "Hello", "pl": "Cześć"}

    def test_get_site_settings_null_fields_fall_back_to_defaults(self):
        repository = _repository(
            {
                "site_content": {
                    "logo_url": None,
                    "favicon_url": None,
                    "primary_color": None,
                    "secondary_color": None,
                    "font": None,
                    "app_description": None,
                }
            }
        )

        settings = repository.get_site_settings()

        assert settings == SiteSettings()

    def test_get_site_settings_defaults(self):
        repository = _repository({"site_content": {}})

        settings = repository.get_site_settings()

        assert settings.logo is None
        assert settings.favicon_url == ""
        assert settings.font == ""
        assert settings.primary_color == "white"
        assert settings.secondary_color == "navy"
        assert settings.app_description == {}

    def test_get_menu_items_in_lang(self):
        repository = _repository(
            {
                "site_content": {
                    "menu_items": {"en": [{"name": "Home", "url": "/"}]},
                }
            }
        )

        menu_items = repository.get_menu_items_in_lang("en")

        assert len(menu_items) == 1
        assert menu_items[0].name == "Home"

    def test_get_menu_items_in_lang_missing(self):
        repository = _repository({"site_content": {}})
        assert repository.get_menu_items_in_lang("en") == []

    def test_get_home_page_path(self):
        repository = _repository({"site_content": {"home_page_path": "/blog/page/about"}})
        assert repository.get_home_page_path("en") == "/blog/page/about"

    def test_get_home_page_path_per_locale(self):
        repository = _repository(
            {
                "site_content": {
                    "home_page_path": {"en": "/en/about", "default": "/about"},
                }
            }
        )
        assert repository.get_home_page_path("en") == "/en/about"
        assert repository.get_home_page_path("pl") == "/about"

    def test_get_home_page_path_default(self):
        repository = _repository({"site_content": {}})
        assert repository.get_home_page_path("en") is None

    def test_get_blog_meta(self):
        blog_meta = {
            "en": {"title": "Reading notes", "description": "Notes on Tolkien's books."},
            "pl": {"title": "Notatki", "description": "Notatki o książkach Tolkiena."},
        }
        repository = _repository({"site_content": {"blog_meta": blog_meta}})
        assert repository.get_blog_meta("en") == PageMeta(**blog_meta["en"])
        assert repository.get_blog_meta("pl").title == "Notatki"
        assert repository.get_blog_meta("fr") == PageMeta()

    def test_get_blog_meta_not_configured(self):
        repository = _repository({"site_content": {}})
        assert repository.get_blog_meta("en") == PageMeta()

    def test_get_footer(self):
        footer = {"content": {"en": "Footer", "pl": "Stopka"}}
        repository = _repository({"site_content": {"footer": footer}})
        assert repository.get_footer("en").content == "Footer"
        assert repository.get_footer("pl").content == "Stopka"
        assert repository.get_footer("fr").content == ""

    def test_get_footer_not_configured(self):
        repository = _repository({"site_content": {}})
        assert repository.get_footer("en") == Footer()

    def test_get_footer_collapsible(self):
        repository = _repository({"site_content": {"footer": {"collapsible": True}}})
        assert repository.get_footer("en").collapsible is True

    def test_get_footer_collapsible_not_configured(self):
        repository = _repository({"site_content": {}})
        assert repository.get_footer("en").collapsible is False
