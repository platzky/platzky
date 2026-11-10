"""MongoDB database implementation."""

from typing import Any

from pydantic import Field
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from platzky.db.db import DB, DBConfig
from platzky.db.mongo_blog_repository import MongoBlogRepository
from platzky.db.mongo_plugin_config_repository import MongoPluginConfigRepository
from platzky.db.mongo_site_config_repository import MongoSiteConfigRepository


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

        # Collection references
        self._site_content: Collection[Any] = self._db.site_content
        self._posts: Collection[Any] = self._db.posts
        self._pages: Collection[Any] = self._db.pages
        self._localized_content: Collection[Any] = self._db.localized_content
        self._plugins: Collection[Any] = self._db.plugins
        self.blog = MongoBlogRepository(self._posts, self._pages)
        self.plugin_config = MongoPluginConfigRepository(self._plugins)
        self._mongo_site_config = MongoSiteConfigRepository(
            self._site_content, self._localized_content
        )
        self._mongo_site_config.validate()
        self.site_config = self._mongo_site_config

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
        self._mongo_site_config.validate()
