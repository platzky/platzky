"""Mongo backend: the SiteConfigRepository contract plus the storage specifics it cannot see."""

from typing import Any
from unittest.mock import Mock

import pytest

from platzky.db.exceptions import InvalidDataError
from platzky.db.mongo_site_config_repository import MongoSiteConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository
from tests.unit_tests.db.site_config_repository_contract import SiteConfigRepositoryContract


def _collection(documents: list[dict[str, Any]]) -> Mock:
    """A collection holding these documents; each has an ``_id``."""

    def find_one(query: dict[str, str]) -> dict[str, Any] | None:
        return next((d for d in documents if d["_id"] == query["_id"]), None)

    return Mock(find_one=find_one, find=lambda: documents)


class TestMongoSiteConfigRepository(SiteConfigRepositoryContract):
    def make_repository(self, site_config: dict[str, Any]) -> SiteConfigRepository:
        # Mongo keeps the site-wide keys in one document, and each language's content in a
        # document of its own.
        config = {k: v for k, v in site_config.items() if k != "localized_content"}
        languages = [
            {"_id": lang, **content}
            for lang, content in site_config.get("localized_content", {}).items()
        ]
        return MongoSiteConfigRepository(
            _collection([{"_id": "config", **config}]), _collection(languages)
        )


def test_validate_lists_the_problems_of_the_config_and_of_every_language():
    repository = MongoSiteConfigRepository(
        _collection([{"_id": "config", "primary_color": ""}]),
        _collection([{"_id": "en", "footer": None}, {"_id": "pl", "unknown": 1}]),
    )

    with pytest.raises(InvalidDataError) as error:
        repository.validate()

    assert str(error.value).splitlines() == [
        "site_config.primary_color: String should have at least 1 character",
        "localized_content.en.footer: Input should be a valid dictionary or instance of Footer",
        "localized_content.pl.unknown: Extra inputs are not permitted",
    ]


def test_validate_accepts_an_empty_database():
    MongoSiteConfigRepository(_collection([]), _collection([])).validate()
