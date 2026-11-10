"""MongoDB database implementation."""

from typing import Any

from pydantic import Field
from pymongo import MongoClient
from pymongo.database import Database
from typing_extensions import override

from platzky.db.blog_repository import BlogRepository
from platzky.db.db import DB, DBConfig
from platzky.db.mongo_blog_repository import MongoBlogRepository
from platzky.db.mongo_plugin_config_repository import MongoPluginConfigRepository
from platzky.db.mongo_site_config_repository import MongoSiteConfigRepository
from platzky.db.plugin_config_repository import PluginConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository


def db_config_type() -> type["MongoDbConfig"]:
    """Return the configuration class for MongoDB database.

    Returns:
        MongoDbConfig class
    """
    return MongoDbConfig


class MongoDbConfig(DBConfig):
    """Configuration for MongoDB database connection."""

    connection_string: str = Field(alias="CONNECTION_STRING")
    database_name: str = Field(alias="DATABASE_NAME")


def db_from_config(config: MongoDbConfig) -> "MongoDB":
    """Create a MongoDB database instance from configuration.

    Args:
        config: MongoDB database configuration

    Returns:
        Configured MongoDB database instance
    """
    return MongoDB(config.connection_string, config.database_name)


class MongoDB(DB):
    """MongoDB database implementation with connection pooling."""

    def __init__(self, connection_string: str, database_name: str):
        """Initialize MongoDB database connection.

        Args:
            connection_string: MongoDB connection URI
            database_name: Name of the database to use
        """
        super().__init__()
        self.connection_string = connection_string
        self.database_name = database_name
        self._client: MongoClient[Any] = MongoClient(connection_string)
        self._db: Database[Any] = self._client[database_name]

        self._blog = MongoBlogRepository(self._db.posts, self._db.pages, self._db.blog_meta)
        self._plugin_config = MongoPluginConfigRepository(self._db.plugins)
        self._site_config = MongoSiteConfigRepository(
            self._db.site_content, self._db.localized_content
        )
        self._validate()

    def _validate(self) -> None:
        """Raise `InvalidSiteContentError` if the site content or the blog meta is invalid."""
        self._site_config.validate()
        self._blog.validate()

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
    def database(self) -> Database[Any]:
        """The pymongo database behind this facade.

        This is the supported extension point for host apps that build their
        own repositories on the same database (their own collections, queries
        and indexes). It stays usable after this facade is gone: the facade
        never closes the shared client.
        """
        return self._db

    def health_check(self) -> None:
        """Perform a health check on the MongoDB database.

        Raises an exception if the database is not accessible or its site content is invalid.
        """
        self._client.admin.command("ping")
        self._validate()
