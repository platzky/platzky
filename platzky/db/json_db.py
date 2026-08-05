"""In-memory JSON database implementation."""

from typing import Any

from pydantic import Field

from platzky.db.db import DB, DBConfig
from platzky.db.json_blog_storage import JsonBlogStorage
from platzky.db.json_document import get_site_content
from platzky.db.json_plugin_config_repository import JsonPluginConfigRepository
from platzky.db.json_site_config_repository import JsonSiteConfigRepository
from platzky.db.json_stores import JsonStore, MemoryStore
from platzky.db.site_config_repository import SiteSettings
from platzky.models import MenuItem, Page, Post
from platzky.plugin.plugin_config import PluginConfigBase


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
        self._store: JsonStore = store
        self._blog_storage = JsonBlogStorage(store)
        # Same dict object as `self._blog_storage.data`, never reassigned after
        # this point (only mutated in place) -- see `JsonBlogStorage` for why
        # that matters (`FileStore.load()` isn't memoized).
        self.data: dict[str, Any] = self._blog_storage.data
        self._plugins = JsonPluginConfigRepository(self.data)
        self._site_config = JsonSiteConfigRepository(self.data)
        self.module_name = "json_db"
        self.db_name = "JsonDb"

    def get_all_posts(self, lang: str) -> list[Post]:
        """Retrieve all posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of Post objects
        """
        return self._blog_storage.posts.get_all(lang)

    def get_post(self, slug: str) -> Post:
        """Returns a post matching the given slug.

        Args:
            slug: URL-friendly identifier for the post

        Returns:
            Post object

        Raises:
            NotFoundError: If posts data is missing or post not found
        """
        return self._blog_storage.posts.get(slug)

    def get_page(self, slug: str) -> Page:
        """Retrieve a page by its slug.

        Args:
            slug: URL-friendly identifier for the page

        Returns:
            Page object

        Raises:
            NotFoundError: If pages data is missing or page not found
        """
        return self._blog_storage.pages.get(slug)

    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of MenuItem objects
        """
        return self._site_config.get_menu_items_in_lang(lang)

    def get_posts_by_tag(self, tag: str, lang: str) -> list[Post]:
        """Retrieve posts filtered by tag and language.

        Returns a list of posts, unlike generators which can only be iterated once.
        """
        return self._blog_storage.posts.get_by_tag(tag, lang)

    def _get_site_content(self) -> dict[str, Any]:
        """Get the site content dictionary from data.

        Returns:
            Site content dictionary

        Raises:
            DBError: If the site_content section is missing from the database
        """
        return get_site_content(self.data)

    def get_site_settings(self) -> SiteSettings:
        """Retrieve branding and description settings for the app.

        Returns:
            The app's site settings.
        """
        return self._site_config.get_site_settings()

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

    def add_comment(self, author_name: str, comment: str, post_slug: str) -> None:
        """Add a new comment to a post.

        Store dates in UTC with timezone info for consistency with MongoDB backend.
        This ensures accurate time delta calculations regardless of server timezone.
        Legacy dates without timezone info are still supported for backward compatibility.

        Args:
            author_name: Name of the comment author
            comment: Comment text content
            post_slug: URL-friendly identifier of the post

        Raises:
            NotFoundError: If post not found
            ReadOnlyStorageError: If the backend does not support writes
        """
        self._blog_storage.posts.add_comment(author_name, comment, post_slug)

    def get_plugins_data(self) -> dict[str, PluginConfigBase]:
        """Retrieve configuration data for all plugins."""
        return self._plugins.get_all()

    def health_check(self) -> None:
        """Perform a health check on the JSON database.

        Raises an exception if the database is not accessible.
        """
        # Try to access site_content to ensure basic structure is valid
        self._get_site_content()
