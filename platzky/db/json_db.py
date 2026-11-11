"""In-memory JSON database implementation."""

from typing import Any

from pydantic import Field
from typing_extensions import override

from platzky.db.blog_repository import BlogRepository
from platzky.db.db import DB, DBConfig
from platzky.db.json_blog_repository import JsonBlogRepository
from platzky.db.json_document import JsonDocument, JsonSection
from platzky.db.json_plugin_config_repository import JsonPluginConfigRepository
from platzky.db.json_site_config_repository import JsonSiteConfigRepository
from platzky.db.json_stores import JsonStore, MemoryStore
from platzky.db.plugin_config_repository import PluginConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository


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

        Raises:
            InvalidDataError: If the site config or the blog section is invalid. The document
                is loaded once and only changes through the repositories, so it is checked only
                here.
        """
        super().__init__()
        document = JsonDocument(store)
        self._document = document
        self._site_config = JsonSiteConfigRepository(JsonSection(document, "site_config"))
        self._blog = JsonBlogRepository(JsonSection(document, "blog"))
        self._plugin_config = JsonPluginConfigRepository(JsonSection(document, "plugins"))

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
        ``document.data`` on each access; every write must go through
        ``document.edit()`` (``with db.document.edit() as data: ...``), which
        holds the write lock and replaces the document once the edit is saved.
        The ``site_config`` section is read once, when the database is built,
        so writes to it take effect only after a restart.
        """
        return self._document

    @override
    def health_check(self) -> None:
        """Do nothing: the document is in memory and was validated when it was loaded."""
