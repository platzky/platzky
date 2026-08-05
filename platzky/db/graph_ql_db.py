"""GraphQL-based database implementation for CMS integration."""

# TODO: Rename file, extract to another library, remove gql and aiohttp from dependencies

import threading

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from pydantic import Field

from platzky.db.db import DB, DBConfig
from platzky.db.graphql_blog_storage import GraphQLBlogStorage
from platzky.db.graphql_plugin_config_repository import GraphQLPluginConfigRepository
from platzky.db.graphql_site_config_repository import GraphQLSiteConfigRepository
from platzky.db.site_config_repository import SiteSettings
from platzky.models import MenuItem, Page, Post
from platzky.plugin.plugin_config import PluginConfigBase


def db_config_type() -> type["GraphQlDbConfig"]:
    """Return the configuration class for GraphQL database.

    Returns:
        GraphQlDbConfig class
    """
    return GraphQlDbConfig


class GraphQlDbConfig(DBConfig):
    """Configuration for GraphQL database connection."""

    endpoint: str = Field(alias="CMS_ENDPOINT")
    token: str = Field(alias="CMS_TOKEN")


def db_from_config(config: GraphQlDbConfig) -> "GraphQL":
    """Create a GraphQL database instance from configuration.

    Args:
        config: GraphQL database configuration

    Returns:
        Configured GraphQL database instance
    """
    return GraphQL(config.endpoint, config.token)


class GraphQL(DB):
    """GraphQL database implementation for CMS integration."""

    def __init__(self, endpoint: str, token: str) -> None:
        """Initialize GraphQL database connection.

        Args:
            endpoint: GraphQL API endpoint URL
            token: Authentication token for the API
        """
        self.module_name = "graph_ql_db"
        self.db_name = "GraphQLDb"
        self._endpoint = endpoint
        self._headers = {"Authorization": "bearer " + token}
        self._local = threading.local()
        self._blog_storage = GraphQLBlogStorage(endpoint, token)
        self._plugins_repository = GraphQLPluginConfigRepository(endpoint, token)
        self._site_config = GraphQLSiteConfigRepository(endpoint, token)
        super().__init__()

    def __getattr__(self, name: str) -> Client:
        """Lazily build this thread's GraphQL client on first access to ``client``.

        AIOHTTPTransport's connect/close cycle tracks a single session flag per
        transport instance; sharing one Client across threads lets a second
        thread's connect() race a first thread's still-open session, raising
        TransportAlreadyConnected. A client per thread avoids that. Implemented via
        __getattr__ rather than a property because DB.__init_subclass__ forbids
        subclasses from adding public class-level names not in the DB interface.
        """
        if name != "client":
            raise AttributeError(name)
        client = getattr(self._local, "client", None)
        if client is None:
            transport = AIOHTTPTransport(url=self._endpoint, headers=self._headers)
            client = Client(transport=transport)
            self._local.client = client
        return client

    def get_all_posts(self, lang: str) -> list[Post]:
        """Retrieve all published posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of Post objects
        """
        return self._blog_storage.posts.get_all(lang)

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
            NotFoundError: If no post exists for the given slug.
        """
        return self._blog_storage.posts.get(slug)

    def get_page(self, slug: str) -> Page:
        """Retrieve a page by its slug.

        Args:
            slug: URL-friendly identifier for the page

        Returns:
            Page object

        Raises:
            NotFoundError: If no page exists for the given slug.
        """
        return self._blog_storage.pages.get(slug)

    def get_posts_by_tag(self, tag: str, lang: str) -> list[Post]:
        """Retrieve posts filtered by tag and language.

        Args:
            tag: Tag name to filter by
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of Post objects
        """
        return self._blog_storage.posts.get_by_tag(tag, lang)

    def add_comment(self, author_name: str, comment: str, post_slug: str) -> None:
        """Add a new comment to a post.

        Args:
            author_name: Name of the comment author
            comment: Comment text content
            post_slug: URL-friendly identifier of the post
        """
        self._blog_storage.posts.add_comment(author_name, comment, post_slug)

    def get_site_settings(self) -> SiteSettings:
        """Retrieve branding and description settings for the app.

        Returns:
            The app's site settings.
        """
        return self._site_config.get_site_settings()

    def get_home_page_path(self, locale: str) -> str | None:
        """Retrieve the site-relative path configured as the site's homepage.

        Each language has its own ``applicationSetups`` entry in the CMS, so the
        homepage path is looked up for the current locale's entry directly.

        Args:
            locale: Language code (e.g., 'en', 'pl') of the current request.

        Returns:
            Homepage path, or None if no homepage override is configured for
            this locale.
        """
        return self._site_config.get_home_page_path(locale)

    def get_plugins_data(self) -> dict[str, PluginConfigBase]:
        """Retrieve configuration data for all plugins."""
        return self._plugins_repository.get_all()

    def health_check(self) -> None:
        """Perform a health check on the GraphQL database.

        Raises an exception if the database is not accessible.
        """
        # Simple query to check connectivity
        health_query = gql("""
            query {
              __typename
            }
            """)
        self.client.execute(health_query)
