"""GraphQL-based database implementation for CMS integration.

TODO: Rename file, extract to another library, remove gql and aiohttp from dependencies.
"""

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError
from pydantic import Field

from platzky.db.db import DB, DBConfig
from platzky.models import Post


def db_config_type():
    """Return the configuration class for GraphQL database."""
    return GraphQlDbConfig


class GraphQlDbConfig(DBConfig):
    """Configuration for GraphQL database connection."""
    endpoint: str = Field(alias="CMS_ENDPOINT")
    token: str = Field(alias="CMS_TOKEN")


def get_db(config: GraphQlDbConfig):
    """Get a GraphQL database instance from configuration."""
    return GraphQL(config.endpoint, config.token)


def db_from_config(config: GraphQlDbConfig):
    """Create a GraphQL database instance from configuration."""
    return GraphQL(config.endpoint, config.token)


def _standarize_comment(
    comment,
):
    """Standardize comment data structure from GraphQL response."""
    return {
        "author": comment["author"],
        "comment": comment["comment"],
        "date": comment["createdAt"],
    }


def _standarize_post(post):
    """Standardize post data structure from GraphQL response."""
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

    def __init__(self, endpoint, token):
        """Initialize GraphQL database connection."""
        self.module_name = "graph_ql_db"
        self.db_name = "GraphQLDb"
        full_token = "bearer " + token
        transport = AIOHTTPTransport(url=endpoint, headers={"Authorization": full_token})
        self.client = Client(transport=transport)
        super().__init__()

    def get_all_posts(self, lang):
        """Retrieve all published posts for a specific language."""
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
        """Retrieve menu items for a specific language."""
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
        """Retrieve a single post by its slug."""
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

    def get_page(self, slug):
        """Retrieve a page by its slug.

        TODO: Cleanup page logic of internationalization (now it depends on translation of slugs).
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
        """Retrieve posts filtered by tag and language."""
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
        """Add a new comment to a post."""
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
        """Get the font configuration for the application."""
        return str("")

    def get_logo_url(self):
        """Retrieve the URL of the application logo."""
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
        """Retrieve the application description for a specific language."""
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
        """Retrieve the URL of the application favicon."""
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
        """Retrieve configuration data for all plugins."""
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
