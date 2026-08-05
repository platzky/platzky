from typing import cast
from unittest.mock import Mock

from platzky.db.mongo_site_config_repository import MongoSiteConfigRepository


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
