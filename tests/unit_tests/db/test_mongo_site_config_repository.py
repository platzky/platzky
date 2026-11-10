"""Mongo backend: the SiteConfigRepository contract plus the storage specifics it cannot see."""

from collections.abc import Mapping
from typing import Any
from unittest.mock import Mock

import pytest

from platzky.db.exceptions import InvalidDataError
from platzky.db.mongo_site_config_repository import MongoSiteConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository
from tests.unit_tests.db.site_config_repository_contract import SiteConfigRepositoryContract


def _collection(documents: Mapping[str, Mapping[str, Any]]) -> Mock:
    def find_one(query: Mapping[str, str], **_: object) -> dict[str, Any] | None:
        document = documents.get(query["_id"])
        return None if document is None else {"_id": query["_id"], **document}

    def find() -> list[dict[str, Any]]:
        return [{"_id": key, **document} for key, document in documents.items()]

    return Mock(find_one=find_one, find=find)


class TestMongoSiteConfigRepository(SiteConfigRepositoryContract):
    def make_repository(self, site_config: dict[str, Any]) -> SiteConfigRepository:
        # Mongo keeps the site-wide keys in one document, and each language's content in a
        # document of its own.
        config = {k: v for k, v in site_config.items() if k != "localized_content"}
        return MongoSiteConfigRepository(
            _collection({"config": config}),
            _collection(site_config.get("localized_content", {})),
        )


def _invalid_repository() -> MongoSiteConfigRepository:
    return MongoSiteConfigRepository(
        _collection({"config": {"primary_color": ""}}),
        _collection({"en": {"footer": None}, "pl": {"unknown": 1}}),
    )


def test_invalid_site_config_read_is_an_invalid_data_error():
    with pytest.raises(InvalidDataError, match=r"site_config\.primary_color"):
        _invalid_repository().get_site_config()


def test_invalid_localized_content_read_is_an_invalid_data_error():
    with pytest.raises(InvalidDataError, match=r"localized_content\.en\.footer"):
        _invalid_repository().get_localized_content("en")


def test_validate_lists_the_problems_of_the_config_and_of_every_language():
    with pytest.raises(InvalidDataError) as error:
        _invalid_repository().validate()

    assert str(error.value).splitlines() == [
        "site_config.primary_color: String should have at least 1 character",
        "localized_content.en.footer: Input should be a valid dictionary or instance of Footer",
        "localized_content.pl.unknown: Extra inputs are not permitted",
    ]


def test_validate_accepts_an_empty_database():
    MongoSiteConfigRepository(_collection({}), _collection({})).validate()
