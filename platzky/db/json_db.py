"""In-memory JSON database implementation."""

import datetime
from collections.abc import Generator
from typing import Any

from pydantic import Field

from platzky.db.db import DB, DBConfig
from platzky.models import MenuItem, Page, Post


def db_config_type() -> type["JsonDbConfig"]:
    """Return the configuration class for JSON database.

    Returns:
        JsonDbConfig class
    """
    return JsonDbConfig


class JsonDbConfig(DBConfig):
    """Configuration for in-memory JSON database."""

    data: dict[str, Any] = Field(alias="DATA")


def get_db(config: dict[str, Any]) -> "Json":
    """Get a JSON database instance from raw configuration.

    Args:
        config: Raw configuration dictionary

    Returns:
        Configured JSON database instance
    """
    json_db_config = JsonDbConfig.model_validate(config)
    return Json(json_db_config.data)


def db_from_config(config: JsonDbConfig) -> "Json":
    """Create a JSON database instance from configuration.

    Args:
        config: JSON database configuration

    Returns:
        Configured JSON database instance
    """
    return Json(config.data)


# TODO: Make all language-specific methods available without language parameter.
# This will allow a default language and if there is one language,
# there will be no need to pass it to the method or in db.
class Json(DB):
    """In-memory JSON database implementation."""

    def __init__(self, data: dict[str, Any]):
        """Initialize JSON database with data dictionary.

        Args:
            data: Dictionary containing all database content
        """
        super().__init__()
        self.data: dict[str, Any] = data
        self.module_name = "json_db"
        self.db_name = "JsonDb"

    def get_app_description(self, lang):
        """Retrieve the application description for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            Application description text or None if not found
        """
        description = self._get_site_content().get("app_description", {})
        return description.get(lang, None)

    def get_all_posts(self, lang):
        """Retrieve all posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of Post objects
        """
        return [
            Post.model_validate(post)
            for post in self._get_site_content().get("posts", ())
            if post["language"] == lang
        ]

    def get_post(self, slug: str) -> Post:
        """Returns a post matching the given slug.

        Args:
            slug: URL-friendly identifier for the post

        Returns:
            Post object

        Raises:
            ValueError: If posts data is missing or post not found
        """
        all_posts = self._get_site_content().get("posts")
        if all_posts is None:
            raise ValueError("Posts data is missing")
        wanted_post = next((post for post in all_posts if post["slug"] == slug), None)
        if wanted_post is None:
            raise ValueError(f"Post with slug {slug} not found")
        return Post.model_validate(wanted_post)

    # TODO: Add test for non-existing page
    def get_page(self, slug: str):
        """Retrieve a page by its slug.

        Args:
            slug: URL-friendly identifier for the page

        Returns:
            Page object

        Raises:
            ValueError: If pages data is missing or page not found
        """
        pages = self._get_site_content().get("pages")
        if pages is None:
            raise ValueError("Pages data is missing")
        list_of_pages = (page for page in pages if page["slug"] == slug)
        wanted_page = next(list_of_pages, None)
        if wanted_page is None:
            raise ValueError(f"Page with slug {slug} not found")
        page = Page.model_validate(wanted_page)
        return page

    def get_menu_items_in_lang(self, lang) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of MenuItem objects
        """
        menu_items_raw = self._get_site_content().get("menu_items", {})
        items_in_lang = menu_items_raw.get(lang, {})

        menu_items_list = [MenuItem.model_validate(x) for x in items_in_lang]
        return menu_items_list

    def get_posts_by_tag(self, tag: str, lang: str) -> Generator[Any, None, None]:
        """Retrieve posts filtered by tag and language.

        Returns a generator for lazy evaluation, unlike get_all_posts() which returns
        a materialized list. The generator can only be iterated once and doesn't
        support len() or indexing. Use list() to materialize if needed.
        """
        return (
            post
            for post in self._get_site_content()["posts"]
            if tag in post["tags"] and post["language"] == lang
        )

    def _get_site_content(self) -> dict[str, Any]:
        """Get the site content dictionary from data.

        Returns:
            Site content dictionary

        Raises:
            ValueError: If site content is not found
        """
        content = self.data.get("site_content")
        if content is None:
            raise ValueError("Content should not be None")
        return content

    def get_logo_url(self):
        """Retrieve the URL of the application logo.

        Returns:
            Logo image URL or empty string if not found
        """
        return self._get_site_content().get("logo_url", "")

    def get_favicon_url(self):
        """Retrieve the URL of the application favicon.

        Returns:
            Favicon URL or empty string if not found
        """
        return self._get_site_content().get("favicon_url", "")

    def get_font(self) -> str:
        """Get the font configuration for the application.

        Returns:
            Font name or empty string if not configured
        """
        return self._get_site_content().get("font", "")

    def get_primary_color(self):
        """Retrieve the primary color for the application theme.

        Returns:
            Primary color value, defaults to 'white'
        """
        return self._get_site_content().get("primary_color", "white")

    def get_secondary_color(self):
        """Retrieve the secondary color for the application theme.

        Returns:
            Secondary color value, defaults to 'navy'
        """
        return self._get_site_content().get("secondary_color", "navy")

    def add_comment(self, author_name, comment, post_slug):
        """Add a new comment to a post.

        Store dates in UTC with timezone info for consistency with MongoDB backend.
        This ensures accurate time delta calculations regardless of server timezone.
        Legacy dates without timezone info are still supported for backward compatibility.

        Args:
            author_name: Name of the comment author
            comment: Comment text content
            post_slug: URL-friendly identifier of the post
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

        comment = {
            "author": str(author_name),
            "comment": str(comment),
            "date": now_utc,
        }

        post_index = next(
            i
            for i in range(len(self._get_site_content()["posts"]))
            if self._get_site_content()["posts"][i]["slug"] == post_slug
        )
        self._get_site_content()["posts"][post_index]["comments"].append(comment)

    def get_plugins_data(self):
        """Retrieve configuration data for all plugins.

        Returns:
            List of plugin configuration dictionaries
        """
        return self.data.get("plugins", [])

    def health_check(self) -> None:
        """Perform a health check on the JSON database.

        Raises an exception if the database is not accessible.
        """
        # Try to access site_content to ensure basic structure is valid
        self._get_site_content()
