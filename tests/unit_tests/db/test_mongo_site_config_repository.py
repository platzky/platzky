"""Mongo storage specifics the contract suite cannot see: which documents are read, and how."""

from unittest.mock import Mock

from platzky.db.mongo_site_config_repository import MongoSiteConfigRepository
from platzky.db.site_config_repository import SiteSettings
from platzky.models import Footer


class TestMongoSiteConfigRepository:
    def test_site_settings_read_only_stored_keys_of_the_config_document(self):
        # The projection keeps the amount of data read from the database small.
        site_content = Mock()
        site_content.find_one.return_value = None
        localized_content = Mock()
        localized_content.find_one.return_value = None
        repository = MongoSiteConfigRepository(site_content, Mock(), localized_content)

        repository.get_site_settings("en")

        site_content.find_one.assert_called_once_with(
            {"_id": "config"}, projection=list(SiteSettings.STORED_KEYS)
        )

    def test_site_settings_read_only_stored_keys_of_the_language_document(self):
        site_content = Mock()
        site_content.find_one.return_value = None
        localized_content = Mock()
        localized_content.find_one.return_value = None
        repository = MongoSiteConfigRepository(site_content, Mock(), localized_content)

        repository.get_site_settings("en")

        localized_content.find_one.assert_called_once_with(
            {"_id": "en"}, projection=list(SiteSettings.STORED_KEYS)
        )

    def test_get_site_settings_ignores_localized_content_inside_config_document(self):
        site_content = Mock()
        site_content.find_one.return_value = {
            "_id": "config",
            "app_name": "Default",
            "localized_content": {"en": {"app_name": "Embedded"}},
        }
        localized_content = Mock()
        localized_content.find_one.return_value = None
        repository = MongoSiteConfigRepository(site_content, Mock(), localized_content)

        assert repository.get_site_settings("en").app_name == "Default"

    def test_get_footer_is_read_in_a_single_query(self):
        # Content and collapsible come from one query, not one round-trip each.
        site_content = Mock()
        site_content.find_one.return_value = {
            "_id": "config",
            "footer": {"content": {"en": "Footer"}, "collapsible": True},
        }
        repository = MongoSiteConfigRepository(site_content, Mock(), Mock())

        assert repository.get_footer("en") == Footer(content="Footer", collapsible=True)
        site_content.find_one.assert_called_once_with({"_id": "config"})
