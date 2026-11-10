"""Abstract base classes for database implementations."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from platzky.db.site_config_repository import SiteSettings
from platzky.models import Footer, MenuItem, Page, PageMeta, Post
from platzky.plugin.plugin_config import PluginConfigBase


class DB(ABC):
    """Abstract base class for all database implementations."""

    config_type: type

    @abstractmethod
    def get_blog_meta(self, lang: str) -> PageMeta:
        """Retrieve the blog index's title and description for a specific language.

        A backend without blog meta support returns an empty ``PageMeta()``.

        Args:
            lang: Language code (e.g., 'en', 'pl')
        """
        pass

    @abstractmethod
    def get_footer(self, lang: str) -> Footer:
        """Retrieve the site-wide footer for a specific language.

        A backend without footer support returns an empty ``Footer()``.

        Args:
            lang: Language code (e.g., 'en', 'pl')
        """
        pass

    @abstractmethod
    def get_all_posts(self, lang: str) -> list[Post]:
        """Retrieve all posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')
        """
        pass

    @abstractmethod
    def get_all_pages(self, lang: str) -> list[Page]:
        """Retrieve all pages for a specific language.

        A backend whose pages carry no language returns an empty list.

        Args:
            lang: Language code (e.g., 'en', 'pl')
        """
        pass

    @abstractmethod
    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')
        """
        pass

    @abstractmethod
    def get_post(self, slug: str) -> Post:
        """Retrieve a single post by its slug.

        Args:
            slug: URL-friendly identifier for the post
        """
        pass

    @abstractmethod
    def get_page(self, slug: str) -> Page:
        """Retrieve a page by its slug.

        Args:
            slug: URL-friendly identifier for the page
        """
        pass

    @abstractmethod
    def get_posts_by_tag(self, tag: str, lang: str) -> list[Post]:
        """Retrieve posts filtered by tag and language.

        Args:
            tag: Tag name to filter by
            lang: Language code (e.g., 'en', 'pl')
        """
        pass

    @abstractmethod
    def add_comment(self, author_name: str, comment: str, post_slug: str) -> None:
        """Add a new comment to a post.

        Args:
            author_name: Name of the comment author
            comment: Comment text content
            post_slug: URL-friendly identifier of the post

        Raises:
            NotFoundError: If the post does not exist.
            ReadOnlyStorageError: If the backend does not support writes.
        """
        pass

    @abstractmethod
    def get_site_settings(self, lang: str) -> SiteSettings:
        """Retrieve branding and site text for the app in a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The app's site settings, with text empty where none is configured.
        """
        pass

    @abstractmethod
    def get_plugins_data(self) -> dict[str, PluginConfigBase]:
        """Retrieve configuration data for all plugins."""
        pass

    @abstractmethod
    def get_home_page_path(self, locale: str) -> str | None:
        """Retrieve the site-relative path to render as the site's homepage.

        Args:
            locale: Language code (e.g., 'en', 'pl') of the current request.

        Returns:
            A path such as "/blog/page/about" or "/blog/some-post", resolved
            against the app's own routes. None if no homepage override is configured
            for this locale.
        """
        pass

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
