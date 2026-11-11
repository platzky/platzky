"""Json backend: runs the SiteConfigRepository contract over an in-memory document."""

from typing import Any

import pytest

from platzky.db.exceptions import InvalidDataError
from platzky.db.json_document import JsonDocument, JsonSection
from platzky.db.json_site_config_repository import JsonSiteConfigRepository
from platzky.db.json_stores import MemoryStore
from platzky.db.site_config_repository import SiteConfig, SiteConfigRepository
from tests.unit_tests.db.site_config_repository_contract import StoredSiteConfigContract


class TestJsonSiteConfigRepository(StoredSiteConfigContract):
    def make_repository(self, site_config: dict[str, Any]) -> SiteConfigRepository:
        return _repository(site_config)


def _repository(site_config: object) -> JsonSiteConfigRepository:
    return JsonSiteConfigRepository(
        JsonSection(JsonDocument(MemoryStore({"site_config": site_config})), "site_config")
    )


def test_unknown_key_is_rejected():
    with pytest.raises(InvalidDataError):
        _repository({"unknown": 1})


@pytest.mark.parametrize(
    "site_config",
    [
        None,
        {"localized_content": {"pl": {"app_name": None}}},
    ],
)
def test_null_is_rejected(site_config: dict[str, Any] | None):
    with pytest.raises(InvalidDataError):
        _repository(site_config)


def test_creation_lists_every_problem_with_its_path():
    with pytest.raises(InvalidDataError) as error:
        _repository(
            {
                "primary_color": "",
                "localized_content": {"pl": {"menu_items": [{"name": "Start"}], "x": 1}},
            }
        )

    assert str(error.value).splitlines() == [
        "site_config.primary_color: String should have at least 1 character",
        "site_config.localized_content.pl.menu_items.0.url: Field required",
        "site_config.localized_content.pl.x: Extra inputs are not permitted",
    ]


def test_missing_section_is_the_defaults():
    repository = JsonSiteConfigRepository(JsonSection(JsonDocument(MemoryStore({})), "site_config"))

    assert repository.get_site_config() == SiteConfig()
