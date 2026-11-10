"""Json backend: the SiteConfigRepository contract over an in-memory document, plus validation."""

from typing import Any

import pytest
from pydantic import ValidationError

from platzky.db.json_document import JsonDocument
from platzky.db.json_site_config_repository import JsonSiteConfigRepository
from platzky.db.json_stores import MemoryStore
from platzky.db.site_config_repository import SiteConfigRepository
from tests.unit_tests.db.site_config_repository_contract import SiteConfigRepositoryContract


def _repository(site_content: dict[str, Any]) -> SiteConfigRepository:
    return JsonSiteConfigRepository(JsonDocument(MemoryStore({"site_content": site_content})))


class TestJsonSiteConfigRepository(SiteConfigRepositoryContract):
    def make_repository(self, site_content: dict[str, Any]) -> SiteConfigRepository:
        return _repository(site_content)

    def test_posts_and_pages_do_not_affect_site_config(self):
        repository = _repository({"posts": [{"title": "Post"}], "pages": [{"title": "Page"}]})

        assert repository.get_home_page_path("en") is None

    def test_removed_top_level_sections_are_rejected(self):
        repository = _repository({"menu_items": {"en": [{"name": "Home", "url": "/"}]}})

        with pytest.raises(ValidationError):
            repository.get_menu_items_in_lang("en")
