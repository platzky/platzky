"""Json backend: runs the SiteConfigRepository contract over an in-memory document."""

from typing import Any

from platzky.db.json_document import JsonDocument
from platzky.db.json_site_config_repository import JsonSiteConfigRepository
from platzky.db.json_stores import MemoryStore
from platzky.db.site_config_repository import SiteConfigRepository
from tests.unit_tests.db.site_config_repository_contract import SiteConfigRepositoryContract


class TestJsonSiteConfigRepository(SiteConfigRepositoryContract):
    def make_repository(self, site_content: dict[str, Any]) -> SiteConfigRepository:
        return JsonSiteConfigRepository(JsonDocument(MemoryStore({"site_content": site_content})))
