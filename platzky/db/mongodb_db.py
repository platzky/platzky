"""MongoDB database implementation."""

import datetime
from typing import Any

from pydantic import Field
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from platzky.db.db import DB, DBConfig
from platzky.models import MenuItem, Page, Post


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


def get_db(config: dict[str, Any]) -> "MongoDB":
    """Get a MongoDB database instance from raw configuration.

    Args:
        config: Raw configuration dictionary

    Returns:
        Configured MongoDB database instance
    """
    mongodb_config = MongoDbConfig.model_validate(config)
    return MongoDB(mongodb_config.connection_string, mongodb_config.database_name)


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

    def get_app_description(self, lang: str) -> str:
        """Retrieve the application description for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            Application description text or empty string if not found
        """
        site_content = self.site_content.find_one({"_id": "config"})
        if site_content and "app_description" in site_content:
            return site_content["app_description"].get(lang, "")
        return ""

    def get_all_posts(self, lang: str) -> list[Post]:
        """Retrieve all posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of Post objects
        """
        posts_cursor = self.posts.find({"language": lang})
        return [Post.model_validate(post) for post in posts_cursor]

    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of MenuItem objects
        """
        menu_items_doc = self.menu_items.find_one({"_id": lang})
        if menu_items_doc and "items" in menu_items_doc:
            return [MenuItem.model_validate(item) for item in menu_items_doc["items"]]
        return []

    def get_post(self, slug: str) -> Post:
        """Retrieve a single post by its slug.

        Args:
            slug: URL-friendly identifier for the post

        Returns:
            Post object

        Raises:
            ValueError: If post not found
        """
        post_doc = self.posts.find_one({"slug": slug})
        if post_doc is None:
            raise ValueError(f"Post with slug {slug} not found")
        return Post.model_validate(post_doc)

    def get_page(self, slug: str) -> Page:
        """Retrieve a page by its slug.

        Args:
            slug: URL-friendly identifier for the page

        Returns:
            Page object

        Raises:
            ValueError: If page not found
        """
        page_doc = self.pages.find_one({"slug": slug})
        if page_doc is None:
            raise ValueError(f"Page with slug {slug} not found")
        return Page.model_validate(page_doc)

    def get_posts_by_tag(self, tag: str, lang: str) -> Any:
        """Retrieve posts filtered by tag and language.

        Args:
            tag: Tag name to filter by
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            MongoDB cursor with matching posts
        """
        posts_cursor = self.posts.find({"tags": tag, "language": lang})
        return posts_cursor

    def add_comment(self, author_name: str, comment: str, post_slug: str) -> None:
        """Add a new comment to a post.

        Args:
            author_name: Name of the comment author
            comment: Comment text content
            post_slug: URL-friendly identifier of the post

        Raises:
            ValueError: If post not found
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        comment_doc = {
            "author": str(author_name),
            "comment": str(comment),
            "date": now_utc,
        }

        result = self.posts.update_one({"slug": post_slug}, {"$push": {"comments": comment_doc}})
        if result.matched_count == 0:
            raise ValueError(f"Post with slug {post_slug} not found")

    def get_logo_url(self) -> str:
        """Retrieve the URL of the application logo.

        Returns:
            Logo image URL or empty string if not found
        """
        site_content = self.site_content.find_one({"_id": "config"})
        if site_content:
            return site_content.get("logo_url", "")
        return ""

    def get_favicon_url(self) -> str:
        """Retrieve the URL of the application favicon.

        Returns:
            Favicon URL or empty string if not found
        """
        site_content = self.site_content.find_one({"_id": "config"})
        if site_content:
            return site_content.get("favicon_url", "")
        return ""

    def get_primary_color(self) -> str:
        """Retrieve the primary color for the application theme.

        Returns:
            Primary color value, defaults to 'white'
        """
        site_content = self.site_content.find_one({"_id": "config"})
        if site_content:
            return site_content.get("primary_color", "white")
        return "white"

    def get_secondary_color(self) -> str:
        """Retrieve the secondary color for the application theme.

        Returns:
            Secondary color value, defaults to 'navy'
        """
        site_content = self.site_content.find_one({"_id": "config"})
        if site_content:
            return site_content.get("secondary_color", "navy")
        return "navy"

    def get_plugins_data(self) -> list[Any]:
        """Retrieve configuration data for all plugins.

        Returns:
            List of plugin configuration dictionaries
        """
        plugins_doc = self.plugins.find_one({"_id": "config"})
        if plugins_doc and "data" in plugins_doc:
            return plugins_doc["data"]
        return []

    def get_font(self) -> str:
        """Get the font configuration for the application.

        Returns:
            Font name or empty string if not configured
        """
        site_content = self.site_content.find_one({"_id": "config"})
        if site_content:
            return site_content.get("font", "")
        return ""

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
