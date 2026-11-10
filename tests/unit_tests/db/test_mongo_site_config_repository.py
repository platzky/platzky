"""Mongo backend: the SiteConfigRepository contract plus the storage specifics it cannot see."""

from collections.abc import Mapping
from typing import Any
from unittest.mock import Mock

from platzky.db.mongo_site_config_repository import MongoSiteConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository
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
