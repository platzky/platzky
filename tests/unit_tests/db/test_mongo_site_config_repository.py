"""Mongo backend: the SiteConfigRepository contract plus the storage specifics it cannot see."""

from collections.abc import Mapping
from typing import Any
from unittest.mock import Mock

from platzky.db.mongo_site_config_repository import MongoSiteConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository, SiteSettings
from platzky.models import Footer
from tests.unit_tests.db.site_config_repository_contract import SiteConfigRepositoryContract


def _collection(documents: Mapping[str, Mapping[str, Any]]) -> Mock:
    def find_one(query: Mapping[str, str], **_: object) -> Mapping[str, Any] | None:
        return documents.get(query["_id"])

    return Mock(find_one=find_one)


class TestMongoSiteConfigRepository(SiteConfigRepositoryContract):
    def make_repository(self, site_content: dict[str, Any]) -> SiteConfigRepository:
        # Mongo keeps the config in one document, and menus and overrides in one
        # document per language.
        config = {k: v for k, v in site_content.items() if k != "localized_content"}
        menu_items = site_content.get("menu_items") or {}
        localized_content = site_content.get("localized_content") or {}
        return MongoSiteConfigRepository(
            _collection({"config": config} if site_content else {}),
            _collection({lang: {"items": items} for lang, items in menu_items.items()}),
            _collection(dict(localized_content)),
        )

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
