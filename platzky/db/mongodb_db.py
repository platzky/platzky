"""MongoDB database implementation."""

from typing import Any

from pydantic import Field
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from typing_extensions import override

from platzky.db.blog_storage import BlogStorage
from platzky.db.db import DB, DBConfig
from platzky.db.mongo_blog_storage import MongoBlogStorage
from platzky.db.mongo_plugin_config_repository import MongoPluginConfigRepository
from platzky.db.mongo_site_config_repository import MongoSiteConfigRepository
from platzky.db.plugin_config_repository import PluginConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository, SiteSettings
from platzky.models import Footer, MenuItem, Page, PageMeta, Post
from platzky.plugin.plugin_config import PluginConfigBase


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
        self.client: MongoClient[Any] = MongoClient(connection_string)
        self.db: Database[Any] = self.client[database_name]
        self.module_name = "mongodb_db"
        self.db_name = "MongoDB"

        # Collection references
        self.site_content: Collection[Any] = self.db.site_content
        self.posts: Collection[Any] = self.db.posts
        self.pages: Collection[Any] = self.db.pages
        self.menu_items: Collection[Any] = self.db.menu_items
        self.plugins: Collection[Any] = self.db.plugins
        self._blog_storage: BlogStorage = MongoBlogStorage(self.posts, self.pages)
        self._plugin_config: PluginConfigRepository = MongoPluginConfigRepository(self.plugins)
        self._site_config: SiteConfigRepository = MongoSiteConfigRepository(
            self.site_content, self.menu_items
        )

    @override
    def get_blog_meta(self, lang: str) -> PageMeta:
        """Retrieve the blog index's title and description for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            The blog meta, empty if none is configured for the language
        """
        return self._site_config.get_blog_meta(lang)

    @override
    def get_footer(self, lang: str) -> Footer:
        """Retrieve the site-wide footer for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            The footer, empty and not collapsible if none is configured
        """
        return self._site_config.get_footer(lang)

    def get_all_posts(self, lang: str) -> list[Post]:
        """Retrieve all posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of Post objects
        """
        return self._blog_storage.posts.get_all(lang)

    @override
    def get_all_pages(self, lang: str) -> list[Page]:
        """Retrieve all pages for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of Page objects
        """
        return self._blog_storage.pages.get_all(lang)

    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of MenuItem objects
        """
        return self._site_config.get_menu_items_in_lang(lang)

    def get_post(self, slug: str) -> Post:
        """Retrieve a single post by its slug.

        Args:
            slug: URL-friendly identifier for the post

        Returns:
            Post object

        Raises:
            NotFoundError: If post not found
        """
        return self._blog_storage.posts.get(slug)

    def get_page(self, slug: str) -> Page:
        """Retrieve a page by its slug.

        Args:
            slug: URL-friendly identifier for the page

        Returns:
            Page object

        Raises:
            NotFoundError: If page not found
        """
        return self._blog_storage.pages.get(slug)

    def get_posts_by_tag(self, tag: str, lang: str) -> list[Post]:
        """Retrieve posts filtered by tag and language.

        Args:
            tag: Tag name to filter by
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of Post objects matching the tag and language
        """
        return self._blog_storage.posts.get_by_tag(tag, lang)

    def add_comment(self, author_name: str, comment: str, post_slug: str) -> None:
        """Add a new comment to a post.

        Args:
            author_name: Name of the comment author
            comment: Comment text content
            post_slug: URL-friendly identifier of the post

        Raises:
            NotFoundError: If post not found
        """
        self._blog_storage.posts.add_comment(author_name, comment, post_slug)

    def get_site_settings(self) -> SiteSettings:
        """Retrieve branding and description settings for the app.

        Returns:
            The app's site settings.
        """
        return self._site_config.get_site_settings()

    def get_plugins_data(self) -> dict[str, PluginConfigBase]:
        """Retrieve configuration data for all plugins."""
        return self._plugin_config.get_all()

    def get_home_page_path(self, locale: str) -> str | None:
        """Retrieve the site-relative path configured as the site's homepage.

        ``home_page_path`` may be a single string (applies to every locale) or a
        dict mapping locale codes to paths, with an optional "default" key used
        when the current locale has no entry of its own.

        Args:
            locale: Language code (e.g., 'en', 'pl') of the current request.

        Returns:
            Homepage path, or None if no homepage override is configured.
        """
        return self._site_config.get_home_page_path(locale)

    def health_check(self) -> None:
        """Perform a health check on the MongoDB database.

        Raises an exception if the database is not accessible.
        """
        # Simple ping to check if database is accessible
        self.client.admin.command("ping")

    def _close_connection(self) -> None:
        """Close the MongoDB connection"""
        if self.client:
            self.client.close()

    def __del__(self):
        """Ensure connection is closed when object is destroyed"""
        self._close_connection()
