"""In-memory JSON database implementation."""

from collections.abc import Mapping
from typing import Any

from pydantic import Field
from typing_extensions import override

from platzky.db.blog_repository import BlogRepository
from platzky.db.db import DB, DBConfig
from platzky.db.exceptions import InvalidDataError
from platzky.db.json_blog_repository import SECTION as BLOG_SECTION
from platzky.db.json_blog_repository import JsonBlogRepository, parse_blog
from platzky.db.json_document import JsonDocument, get_section
from platzky.db.json_plugin_config_repository import JsonPluginConfigRepository
from platzky.db.json_site_config_repository import SECTION as SITE_CONFIG_SECTION
from platzky.db.json_site_config_repository import JsonSiteConfigRepository, parse_site_config
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
def validate_json_document(document: Mapping[str, Any]) -> None:
    """Validate the ``site_config`` and ``blog`` sections of a JSON document.

    The ``site_config`` section is required; an absent ``blog`` section is an empty blog. Plugin
    settings are not checked.

    Args:
        document: The loaded document.

    Raises:
        InvalidDataError: If a section is invalid; the message lists every problem with its
            path, one per line.
    """
    errors: list[str] = []
    try:
        parse_site_config(document.get(SITE_CONFIG_SECTION))
    except InvalidDataError as error:
        errors.append(str(error))
    try:
        parse_blog(document.get(BLOG_SECTION, {}))
    except InvalidDataError as error:
        errors.append(str(error))
    if errors:
        raise InvalidDataError("\n".join(errors))


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
        if SITE_CONFIG_SECTION in document.data:
            validate_json_document(document.data)

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

        Raises an exception if the database is not accessible, has no ``site_config`` section,
        or a section is invalid.
        """
        get_section(self._document.data, SITE_CONFIG_SECTION)
        validate_json_document(self._document.data)
