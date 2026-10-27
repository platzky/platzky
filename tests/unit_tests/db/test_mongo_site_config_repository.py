from typing import cast
from unittest.mock import Mock

from platzky.db.mongo_site_config_repository import MongoSiteConfigRepository
from platzky.db.site_config_repository import SiteSettings
from platzky.models import Footer, PageMeta


class TestMongoSiteConfigRepository:
    def test_get_site_settings(self):
        site_content = Mock()
        cast(Mock, site_content.find_one).return_value = {
            "_id": "config",
            "logo_url": "/logo.png",
            "favicon_url": "/favicon.ico",
            "font": "Arial",
            "primary_color": "blue",
            "secondary_color": "green",
            "app_description": {"en": "Hello"},
        }
        repository = MongoSiteConfigRepository(site_content, Mock())

        settings = repository.get_site_settings()

        assert settings.logo is not None
        assert settings.logo.url == "/logo.png"
        assert settings.favicon_url == "/favicon.ico"
        assert settings.font == "Arial"
        assert settings.primary_color == "blue"
        assert settings.secondary_color == "green"
        assert settings.app_description == {"en": "Hello"}
        cast(Mock, site_content.find_one).assert_called_once_with({"_id": "config"})

    def test_get_site_settings_defaults_when_no_document(self):
        site_content = Mock()
        cast(Mock, site_content.find_one).return_value = None
        repository = MongoSiteConfigRepository(site_content, Mock())

        settings = repository.get_site_settings()

        assert settings.logo is None
        assert settings.favicon_url == ""
        assert settings.font == ""
        assert settings.primary_color == "white"
        assert settings.secondary_color == "navy"
        assert settings.app_description == {}

    def test_get_menu_items_in_lang(self):
        menu_items = Mock()
        cast(Mock, menu_items.find_one).return_value = {
            "_id": "en",
            "items": [{"name": "Home", "url": "/"}],
        }
        repository = MongoSiteConfigRepository(Mock(), menu_items)

        result = repository.get_menu_items_in_lang("en")

        assert len(result) == 1
        assert result[0].name == "Home"
        cast(Mock, menu_items.find_one).assert_called_once_with({"_id": "en"})

    def test_get_menu_items_in_lang_no_data(self):
        menu_items = Mock()
        cast(Mock, menu_items.find_one).return_value = None
        repository = MongoSiteConfigRepository(Mock(), menu_items)

        assert repository.get_menu_items_in_lang("en") == []

    def test_get_home_page_path(self):
        site_content = Mock()
        cast(Mock, site_content.find_one).return_value = {
            "_id": "config",
            "home_page_path": "/blog/page/about",
        }
        repository = MongoSiteConfigRepository(site_content, Mock())

        assert repository.get_home_page_path("en") == "/blog/page/about"

    def test_get_home_page_path_no_document(self):
        site_content = Mock()
        cast(Mock, site_content.find_one).return_value = None
        repository = MongoSiteConfigRepository(site_content, Mock())

        assert repository.get_home_page_path("en") is None

    def test_get_site_settings_null_fields_fall_back_to_defaults(self):
        site_content = Mock()
        cast(Mock, site_content.find_one).return_value = {
            "_id": "config",
            "logo_url": None,
            "favicon_url": None,
            "primary_color": None,
            "secondary_color": None,
            "font": None,
            "app_description": None,
        }
        repository = MongoSiteConfigRepository(site_content, Mock())

        assert repository.get_site_settings() == SiteSettings()

    def test_get_blog_meta(self):
        site_content = Mock()
        cast(Mock, site_content.find_one).return_value = {
            "_id": "config",
            "blog_meta": {"en": {"title": "Reading notes", "description": "On Tolkien."}},
        }
        repository = MongoSiteConfigRepository(site_content, Mock())

        assert repository.get_blog_meta("en") == PageMeta(
            title="Reading notes", description="On Tolkien."
        )
        assert repository.get_blog_meta("pl") == PageMeta()

    def test_get_blog_meta_no_data(self):
        site_content = Mock()
        cast(Mock, site_content.find_one).return_value = None
        repository = MongoSiteConfigRepository(site_content, Mock())

        assert repository.get_blog_meta("en") == PageMeta()

    def test_get_footer(self):
        site_content = Mock()
        find_one = cast(Mock, site_content.find_one)
        find_one.return_value = {
            "_id": "config",
            "footer": {"content": {"en": "Footer", "pl": "Stopka"}},
        }
        repository = MongoSiteConfigRepository(site_content, Mock())

        assert repository.get_footer("en").content == "Footer"
        assert repository.get_footer("pl").content == "Stopka"
        assert repository.get_footer("fr").content == ""
        find_one.assert_called_with({"_id": "config"})

    def test_get_footer_not_configured(self):
        site_content = Mock()
        cast(Mock, site_content.find_one).return_value = {"_id": "config"}
        repository = MongoSiteConfigRepository(site_content, Mock())

        assert repository.get_footer("en") == Footer()
        assert repository.get_footer("en").collapsible is False

    def test_get_footer_no_data(self):
        site_content = Mock()
        cast(Mock, site_content.find_one).return_value = None
        repository = MongoSiteConfigRepository(site_content, Mock())

        assert repository.get_footer("en") == Footer()

    def test_get_footer_is_read_in_a_single_query(self):
        site_content = Mock()
        find_one = cast(Mock, site_content.find_one)
        find_one.return_value = {
            "_id": "config",
            "footer": {"content": {"en": "Footer"}, "collapsible": True},
        }
        repository = MongoSiteConfigRepository(site_content, Mock())

        assert repository.get_footer("en") == Footer(content="Footer", collapsible=True)
        find_one.assert_called_once_with({"_id": "config"})
