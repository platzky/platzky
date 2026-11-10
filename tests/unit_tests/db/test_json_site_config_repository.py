"""Json backend: runs the SiteConfigRepository contract over an in-memory document."""

from typing import Any

import pytest

from platzky.db.exceptions import InvalidSiteContentError
from platzky.db.json_document import JsonDocument
from platzky.db.json_site_config_repository import JsonSiteConfigRepository
from platzky.db.json_stores import MemoryStore
from platzky.db.site_config_repository import SiteConfigRepository
from tests.unit_tests.db.site_config_repository_contract import SiteConfigRepositoryContract


class TestJsonSiteConfigRepository(SiteConfigRepositoryContract):
    def make_repository(self, site_content: dict[str, Any]) -> SiteConfigRepository:
        return JsonSiteConfigRepository(JsonDocument(MemoryStore({"site_content": site_content})))


def _invalid_repository() -> SiteConfigRepository:
    site_content = {"primary_color": "", "localized_content": {"en": {"footer": None}}}
    return JsonSiteConfigRepository(JsonDocument(MemoryStore({"site_content": site_content})))


def test_invalid_site_content_read_is_an_invalid_site_content_error():
    with pytest.raises(InvalidSiteContentError, match=r"site_content\.primary_color"):
        _invalid_repository().get_site_content()


def test_invalid_localized_content_read_is_an_invalid_site_content_error():
    with pytest.raises(InvalidSiteContentError, match=r"site_content\.localized_content\.en"):
        _invalid_repository().get_localized_content("en")
