"""Abstract base classes for database implementations."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from platzky.db.blog_repository import BlogRepository
from platzky.db.plugin_config_repository import PluginConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository


class DB(ABC):
    """Abstract base class for all database implementations.

    A database is a container of three repositories; backends build them in
    their constructor and expose them as these attributes.
    """

    config_type: type
    blog: BlogRepository
    site_config: SiteConfigRepository
    plugin_config: PluginConfigRepository

    @abstractmethod
    def health_check(self) -> None:
        """Perform a health check on the database.

        Should raise an exception if the database is not healthy.
        This should be a lightweight operation suitable for health checks.
        """
        pass


class DBConfig(BaseModel):
    """Base configuration class for database connections."""

    type: str = Field(alias="TYPE")
