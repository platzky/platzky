"""GraphQL-based database implementation for CMS integration."""

# TODO: Rename file, extract to another library, remove gql and aiohttp from dependencies

from typing import Any

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError
from pydantic import Field

from platzky.db.db import DB, DBConfig
from platzky.models import Post


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


def get_db(config: GraphQlDbConfig) -> "GraphQL":
    """Get a GraphQL database instance from configuration.

    Args:
        config: GraphQL database configuration

    Returns:
        Configured GraphQL database instance
    """
    return GraphQL(config.endpoint, config.token)


def db_from_config(config: GraphQlDbConfig) -> "GraphQL":
    """Create a GraphQL database instance from configuration.

    Args:
        config: GraphQL database configuration

    Returns:
        Configured GraphQL database instance
    """
    return GraphQL(config.endpoint, config.token)


def _standarize_comment(
    comment: dict[str, Any],
) -> dict[str, Any]:
    """Standardize comment data structure from GraphQL response.

    Args:
        comment: Raw comment data from GraphQL response

    Returns:
        Standardized comment dictionary
    """
    return {
        "author": comment["author"],
        "comment": comment["comment"],
        "date": comment["createdAt"],
    }


def _standarize_post(post: dict[str, Any]) -> dict[str, Any]:
    """Standardize post data structure from GraphQL response.

    Args:
        post: Raw post data from GraphQL response

    Returns:
        Standardized post dictionary
    """
    return {
        "author": post["author"]["name"],
        "slug": post["slug"],
        "title": post["title"],
        "excerpt": post["excerpt"],
        "contentInMarkdown": post["contentInRichText"]["html"],
        "comments": [_standarize_comment(comment) for comment in post["comments"]],
        "tags": post["tags"],
        "language": post["language"],
        "coverImage": {
            "url": post["coverImage"]["image"]["url"],
        },
        "date": post["date"],
    }


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
        full_token = "bearer " + token
        transport = AIOHTTPTransport(url=endpoint, headers={"Authorization": full_token})
        self.client = Client(transport=transport)
        super().__init__()

    def get_all_posts(self, lang):
        """Retrieve all published posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of Post objects
        """
        all_posts = gql(
            """
            query MyQuery($lang: Lang!) {
              posts(where: {language: $lang},  orderBy: date_DESC, stage: PUBLISHED){
                createdAt
                author {
                    name
                }
                contentInRichText {
                    html
                    }
                comments {
                  comment
                  author
                  createdAt
                  }
                date
                title
                excerpt
                slug
                tags
                language
                coverImage {
                  alternateText
                  image {
                    url
                  }
                }
              }
            }
            """
        )
        raw_ql_posts = self.client.execute(all_posts, variable_values={"lang": lang})["posts"]

        return [Post.model_validate(_standarize_post(post)) for post in raw_ql_posts]

    def get_menu_items_in_lang(self, lang):
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of menu item dictionaries
        """
        menu_items = []
        try:
            menu_items_with_lang = gql(
                """
                query MyQuery($lang: Lang!) {
                  menuItems(where: {language: $lang}, stage: PUBLISHED){
                    name
                    url
                  }
                }
                """
            )
            menu_items = self.client.execute(
                menu_items_with_lang, variable_values={"language": lang}
            )

        # TODO remove try except block after bumping up version
        # now it's backwards compatible with older versions
        except TransportQueryError:
            menu_items_without_lang = gql(
                """
                query MyQuery {
                  menuItems(stage: PUBLISHED){
                    name
                    url
                  }
                }
                """
            )
            menu_items = self.client.execute(menu_items_without_lang)

        return menu_items["menuItems"]

    def get_post(self, slug):
        """Retrieve a single post by its slug.

        Args:
            slug: URL-friendly identifier for the post

        Returns:
            Post object
        """
        post = gql(
            """
            query MyQuery($slug: String!) {
              post(where: {slug: $slug}, stage: PUBLISHED) {
                date
                language
                title
                slug
                author {
                    name
                }
                contentInRichText {
                  markdown
                  html
                }
                excerpt
                tags
                coverImage {
                  alternateText
                  image {
                    url
                  }
                }
                comments {
                    author
                    comment
                    date: createdAt
                }
              }
            }
            """
        )

        post_raw = self.client.execute(post, variable_values={"slug": slug})["post"]
        return Post.model_validate(_standarize_post(post_raw))

    # TODO: Cleanup page logic of internationalization (now it depends on translation of slugs)
    def get_page(self, slug):
        """Retrieve a page by its slug.

        Args:
            slug: URL-friendly identifier for the page

        Returns:
            Page dictionary
        """
        post = gql(
            """
            query MyQuery ($slug: String!){
              page(where: {slug: $slug}, stage: PUBLISHED) {
                title
                contentInMarkdown
                coverImage
                {
                    url
                }
              }
            }
            """
        )
        return self.client.execute(post, variable_values={"slug": slug})["page"]

    def get_posts_by_tag(self, tag, lang):
        """Retrieve posts filtered by tag and language.

        Args:
            tag: Tag name to filter by
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of post dictionaries
        """
        post = gql(
            """
            query MyQuery ($tag: String!, $lang: Lang!){
              posts(where: {tags_contains_some: [$tag], language: $lang}, stage: PUBLISHED) {
                    tags
                    title
                    slug
                    excerpt
                    date
                    coverImage {
                      alternateText
                      image {
                        url
                      }
                    }
              }
            }
            """
        )
        return self.client.execute(post, variable_values={"tag": tag, "lang": lang})["posts"]

    def add_comment(self, author_name, comment, post_slug):
        """Add a new comment to a post.

        Args:
            author_name: Name of the comment author
            comment: Comment text content
            post_slug: URL-friendly identifier of the post
        """
        add_comment = gql(
            """
            mutation MyMutation($author: String!, $comment: String!, $slug: String!) {
                createComment(
                    data: {
                        author: $author,
                        comment: $comment,
                        post: {connect: {slug: $slug}}
                    }
                ) {
                    id
                }
            }
            """
        )
        self.client.execute(
            add_comment,
            variable_values={
                "author": author_name,
                "comment": comment,
                "slug": post_slug,
            },
        )

    def get_font(self):
        """Get the font configuration for the application.

        Returns:
            Empty string (not implemented in GraphQL backend)
        """
        return ""

    def get_logo_url(self):
        """Retrieve the URL of the application logo.

        Returns:
            Logo image URL or empty string if not found
        """
        logo = gql(
            """
            query myquery {
              logos(stage: PUBLISHED) {
              logo {
                  alternateText
                  image {
                    url
                  }
                }
              }
            }
            """
        )
        try:
            return self.client.execute(logo)["logos"][0]["logo"]["image"]["url"]
        except IndexError:
            return ""

    def get_app_description(self, lang):
        """Retrieve the application description for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            Application description text or None if not found
        """
        description_query = gql(
            """
            query myquery($lang: Lang!) {
              applicationSetups(where: {language: $lang}, stage: PUBLISHED) {
                applicationDescription
              }
            }
            """
        )

        return self.client.execute(description_query, variable_values={"lang": lang})[
            "applicationSetups"
        ][0].get("applicationDescription", None)

    def get_favicon_url(self):
        """Retrieve the URL of the application favicon.

        Returns:
            Favicon URL
        """
        favicon = gql(
            """
            query myquery {
              favicons(stage: PUBLISHED) {
              favicon {
                url
                }
              }
            }
            """
        )

        return self.client.execute(favicon)["favicons"][0]["favicon"]["url"]

    def get_primary_color(self) -> str:
        return "white"  # Default color as string

    def get_secondary_color(self) -> str:
        return "navy"  # Default color as string

    def get_plugins_data(self):
        """Retrieve configuration data for all plugins.

        Returns:
            List of plugin configuration dictionaries
        """
        plugins_data = gql(
            """
            query MyQuery {
              pluginConfigs(stage: PUBLISHED) {
                name
                config
              }
            }
            """
        )
        return self.client.execute(plugins_data)["pluginConfigs"]

    def health_check(self) -> None:
        """Perform a health check on the GraphQL database.

        Raises an exception if the database is not accessible.
        """
        # Simple query to check connectivity
        health_query = gql(
            """
            query {
              __typename
            }
            """
        )
        self.client.execute(health_query)
