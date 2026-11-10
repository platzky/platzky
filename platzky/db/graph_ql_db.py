"""GraphQL-based database implementation for CMS integration."""

# TODO: Rename file, extract to another library, remove gql and aiohttp from dependencies


from gql import gql
from pydantic import Field

from platzky.db.db import DB, DBConfig
from platzky.db.graphql_blog_repository import GraphQLBlogRepository
from platzky.db.graphql_client import make_graphql_client_getter
from platzky.db.graphql_plugin_config_repository import GraphQLPluginConfigRepository
from platzky.db.graphql_site_config_repository import GraphQLSiteConfigRepository


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
        # One lazy, per-thread client source shared by this facade and every
        # repository, so the endpoint is only ever connected to through it.
        self._client_getter = make_graphql_client_getter(endpoint, token)
        self.blog = GraphQLBlogRepository(self._client_getter)
        self.plugin_config = GraphQLPluginConfigRepository(self._client_getter)
        self.site_config = GraphQLSiteConfigRepository(self._client_getter)
        super().__init__()

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
        self._client_getter().execute(health_query)
