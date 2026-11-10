"""Mongo backend: the SiteConfigRepository contract plus the storage specifics it cannot see."""

from collections.abc import Mapping
from typing import Any
from unittest.mock import Mock

import pytest

from platzky.db.exceptions import InvalidSiteContentError
from platzky.db.mongo_site_config_repository import MongoSiteConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository
from platzky.models import Footer
from tests.unit_tests.db.site_config_repository_contract import SiteConfigRepositoryContract


def _collection(documents: Mapping[str, Mapping[str, Any]]) -> Mock:
    def find_one(query: Mapping[str, str], **_: object) -> dict[str, Any] | None:
        document = documents.get(query["_id"])
        return None if document is None else {"_id": query["_id"], **document}

    return Mock(find_one=find_one)


class TestMongoSiteConfigRepository(SiteConfigRepositoryContract):
    def make_repository(self, site_content: dict[str, Any]) -> SiteConfigRepository:
        # Mongo keeps the site-wide keys in one document, and each language's content in a
        # document of its own.
        config = {k: v for k, v in site_content.items() if k != "localized_content"}
        return MongoSiteConfigRepository(
            _collection({"config": config}),
            _collection(site_content.get("localized_content", {})),
        )

    def test_get_footer_is_read_in_a_single_query_of_the_language_document(self):
        # Content and collapsible come from one query, not one round-trip each.
        site_content = Mock()
        localized_content = Mock()
        localized_content.find_one.return_value = {
            "_id": "en",
            "footer": {"content": "Footer", "collapsible": True},
        }
        repository = MongoSiteConfigRepository(site_content, localized_content)

        assert repository.get_footer("en") == Footer(content="Footer", collapsible=True)
        localized_content.find_one.assert_called_once_with({"_id": "en"})
        site_content.find_one.assert_not_called()

    def test_validate_reads_every_document_and_reports_unknown_keys(self):
        site_content = Mock()
        site_content.find_one.return_value = {"_id": "config", "menu_items": {}}
        localized_content = Mock()
        localized_content.find.return_value = [{"_id": "pl", "x": 1}, {"_id": "en"}]
        repository = MongoSiteConfigRepository(site_content, localized_content)

        with pytest.raises(InvalidSiteContentError):
            repository.validate()

        site_content.find_one.assert_called_once_with({"_id": "config"})

    def test_validate_accepts_valid_documents(self):
        site_content = Mock()
        site_content.find_one.return_value = {"_id": "config", "app_name": "Literature"}
        localized_content = Mock()
        localized_content.find.return_value = [{"_id": "pl", "app_name": "Literatura"}]

        MongoSiteConfigRepository(site_content, localized_content).validate()
