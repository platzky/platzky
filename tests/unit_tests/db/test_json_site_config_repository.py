"""Json backend: runs the SiteConfigRepository contract over an in-memory document."""

from typing import Any

import pytest
from pydantic import ValidationError

from platzky.db.exceptions import InvalidDataError
from platzky.db.json_document import JsonDocument
from platzky.db.json_site_config_repository import JsonSiteConfigRepository, parse_site_config
from platzky.db.json_stores import MemoryStore
from platzky.db.site_config_repository import LocalizedContent, SiteConfigRepository
from tests.unit_tests.db.site_config_repository_contract import SiteConfigRepositoryContract


class TestJsonSiteConfigRepository(SiteConfigRepositoryContract):
    def make_repository(self, site_config: dict[str, Any]) -> SiteConfigRepository:
        return JsonSiteConfigRepository(JsonDocument(MemoryStore({"site_config": site_config})))


def _invalid_repository() -> SiteConfigRepository:
    site_config = {"primary_color": "", "localized_content": {"en": {"footer": None}}}
    return JsonSiteConfigRepository(JsonDocument(MemoryStore({"site_config": site_config})))


def test_invalid_site_config_read_is_an_invalid_site_config_error():
    with pytest.raises(InvalidDataError, match=r"site_config\.primary_color"):
        _invalid_repository().get_site_config()


def test_invalid_localized_content_read_is_an_invalid_site_config_error():
    with pytest.raises(InvalidDataError, match=r"site_config\.localized_content\.en"):
        _invalid_repository().get_localized_content("en")


@pytest.mark.parametrize(
    "site_config",
    [
        {"posts": []},
        {"pages": []},
        {"blog_meta": {}},
        {"menu_items": {"en": []}},
        {"localized_content": {"en": {"blog_meta": {"title": "Notes"}}}},
        {"footer": {"content": {"en": "Footer"}}},
        {"home_page_path": "/blog/page/about"},
        {"unknown": 1},
        {"localized_content": {"en": {"unknown": 1}}},
    ],
)
def test_unknown_keys_are_rejected(site_config: dict[str, Any]):
    with pytest.raises(InvalidDataError):
        parse_site_config(site_config)


@pytest.mark.parametrize(
    "site_config",
    [
        None,
        {"app_name": None},
        {"localized_content": None},
        {"localized_content": {"pl": None}},
        {"localized_content": {"pl": {"app_name": None}}},
        {"localized_content": {"pl": {"footer": None}}},
        {"localized_content": {"pl": {"menu_items": None}}},
        {"localized_content": {"pl": {"home_page_path": None}}},
    ],
)
def test_null_is_rejected(site_config: dict[str, Any] | None):
    with pytest.raises(InvalidDataError):
        parse_site_config(site_config)


def test_parsed_site_config_is_immutable():
    section = parse_site_config({"localized_content": {"en": {}}})

    with pytest.raises(ValidationError):
        section.app_name = "Changed"
    with pytest.raises(TypeError):
        section.localized_content["pl"] = LocalizedContent()  # type: ignore[index]
