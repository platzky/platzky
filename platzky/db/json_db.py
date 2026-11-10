"""In-memory JSON database implementation."""

from typing import Any

from pydantic import Field
from typing_extensions import override

from platzky.db.blog_repository import BlogRepository
from platzky.db.db import DB, DBConfig
from platzky.db.json_blog_repository import JsonBlogRepository
from platzky.db.json_document import JsonDocument, get_site_content
from platzky.db.json_plugin_config_repository import JsonPluginConfigRepository
from platzky.db.json_site_config_repository import JsonSiteConfigRepository
from platzky.db.json_stores import JsonStore, MemoryStore
from platzky.db.plugin_config_repository import PluginConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository, parse_site_content


def db_config_type() -> type["JsonDbConfig"]:
    """Return the configuration class for JSON database.

    Returns:
        JsonDbConfig class
    """
    return JsonDbConfig


class JsonDbConfig(DBConfig):
    """Configuration for in-memory JSON database."""

    data: dict[str, Any] = Field(alias="DATA")


def db_from_config(config: JsonDbConfig) -> "Json":
    """Create a JSON database instance from configuration.

    Args:
        config: JSON database configuration

    Returns:
        Configured JSON database instance
    """
    return Json(MemoryStore(config.data))


# TODO: Make all language-specific methods available without language parameter.
# This will allow a default language and if there is one language,
# there will be no need to pass it to the method or in db.
class Json(DB):
    """In-memory JSON database implementation."""

    def __init__(self, store: JsonStore) -> None:
        """Initialize JSON database from a storage transport.

        Args:
            store: Storage transport to load the document from and persist
                writes to. The plain in-memory backend uses a `MemoryStore`;
                subclasses that back onto an external resource (a file, a
                bucket, ...) pass their own.
        """
        super().__init__()
        document = JsonDocument(store)
        self._document = document
        self._blog = JsonBlogRepository(document)
        self._plugin_config = JsonPluginConfigRepository(document)
        self._site_config = JsonSiteConfigRepository(document)
        if "site_content" in document.data:
            self._validate_site_content()

    def _validate_site_content(self) -> None:
        """Raise `InvalidSiteContentError` if the site content does not match its format."""
        parse_site_content(get_site_content(self._document.data))

    @property
    @override
    def blog(self) -> BlogRepository:
        """The blog repository."""
        return self._blog

    @property
    @override
    def site_config(self) -> SiteConfigRepository:
        """The site config repository."""
        return self._site_config

    @property
    @override
    def plugin_config(self) -> PluginConfigRepository:
        """The plugin config repository."""
        return self._plugin_config

    @property
    def document(self) -> JsonDocument:
        """The loaded JSON document behind this database.

        This is the supported extension point for host apps that build their
        own repositories on the same storage. Read the dict through
        ``document.data``; every write must go through ``document.edit()``
        (``with db.document.edit() as data: ...``), which holds the write lock
        and persists atomically.
        """
        return self._document

    def health_check(self) -> None:
        """Perform a health check on the JSON database.

        Raises an exception if the database is not accessible or its site content is invalid.
        """
        self._validate_site_content()
