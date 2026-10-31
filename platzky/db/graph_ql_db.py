"""GraphQL-based database implementation for CMS integration."""

# TODO: Rename file, extract to another library, remove gql and aiohttp from dependencies

from typing import Any

from gql import gql
from pydantic import Field
from typing_extensions import override

from platzky.db.db import DB, DBConfig
from platzky.db.exceptions import NotFoundError
from platzky.db.graphql_client import make_graphql_client_getter
from platzky.db.graphql_plugin_config_repository import GraphQLPluginConfigRepository
from platzky.db.graphql_site_config_repository import GraphQLSiteConfigRepository
from platzky.db.plugin_config_repository import PluginConfigRepository
from platzky.db.site_config_repository import SiteConfigRepository, SiteSettings
from platzky.models import Footer, MenuItem, Page, PageMeta, Post
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


def _standardize_comment(
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


def _standardize_post(post: dict[str, Any]) -> dict[str, Any]:
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
        "comments": [_standardize_comment(comment) for comment in post["comments"]],
        "tags": post["tags"],
        "language": post["language"],
        "coverImage": {
            "url": (post.get("coverImage") or {}).get("image", {}).get("url", ""),
        },
        "date": post["date"],
        "css": post.get("css") or "",
    }


def _standardize_page(page: dict[str, Any]) -> dict[str, Any]:
    """Standardize page data structure from GraphQL response.

    Pages have fewer required fields than posts in the GraphQL schema.
    This function provides sensible defaults for missing Post fields.

    Args:
        page: Raw page data from GraphQL response

    Returns:
        Standardized page dictionary compatible with Page model
    """
    return {
        "author": page.get("author", ""),
        "slug": page.get("slug", ""),
        "title": page["title"],
        "excerpt": page.get("excerpt", ""),
        "contentInMarkdown": page["contentInMarkdown"],
        "comments": [],
        "tags": page.get("tags", []),
        "language": page.get("language", "en"),
        "coverImage": {
            "url": (page.get("coverImage") or {}).get("url", ""),
        },
        "date": page.get("date"),
        "css": page.get("css") or "",
    }


def _standardize_post_by_tag(post: dict[str, Any]) -> dict[str, Any]:
    """Standardize post data from get_posts_by_tag GraphQL response.

    Posts returned by tag query have fewer fields than full posts.
    This function provides sensible defaults for missing Post fields.

    Args:
        post: Raw post data from GraphQL get_posts_by_tag response

    Returns:
        Standardized post dictionary compatible with Post model
    """
    return {
        "author": post.get("author", ""),
        "slug": post["slug"],
        "title": post["title"],
        "excerpt": post["excerpt"],
        "contentInMarkdown": post.get("contentInMarkdown", ""),
        "comments": [],
        "tags": post["tags"],
        "language": post.get("language", "en"),
        "coverImage": {
            "url": (post.get("coverImage") or {}).get("image", {}).get("url", ""),
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
        # One lazy, per-thread client source shared by this facade and every
        # repository, so the endpoint is only ever connected to through it.
        self._client_getter = make_graphql_client_getter(endpoint, token)
        self._plugin_config: PluginConfigRepository = GraphQLPluginConfigRepository(
            self._client_getter
        )
        self._site_config: SiteConfigRepository = GraphQLSiteConfigRepository(self._client_getter)
        super().__init__()

    def get_all_posts(self, lang: str) -> list[Post]:
        """Retrieve all published posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of Post objects
        """
        all_posts = gql("""
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
            """)
        raw_ql_posts = self._client_getter().execute(all_posts, variable_values={"lang": lang})[
            "posts"
        ]

        return [Post.model_validate(_standardize_post(post)) for post in raw_ql_posts]

    @override
    def get_all_pages(self, lang: str) -> list[Page]:
        """Retrieve all pages for a specific language.

        Pages here carry no language (they are translated through their slugs), so they
        cannot be listed per language; this queries nothing.

        Args:
            lang: Language code (e.g., 'en', 'pl'), unused

        Returns:
            An empty list
        """
        return []

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
        post = gql("""
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
                css
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
            """)

        post_raw = self._client_getter().execute(post, variable_values={"slug": slug})["post"]
        if post_raw is None:
            raise NotFoundError(f"Post not found: {slug}")
        return Post.model_validate(_standardize_post(post_raw))

    def get_page(self, slug: str) -> Page:
        """Retrieve a page by its slug.

        Args:
            slug: URL-friendly identifier for the page

        Returns:
            Page object

        Raises:
            NotFoundError: If no page exists for the given slug.
        """
        page_query = gql("""
            query MyQuery ($slug: String!){
              page(where: {slug: $slug}, stage: PUBLISHED) {
                slug
                title
                contentInMarkdown
                css
                coverImage
                {
                    url
                }
              }
            }
            """)
        page_raw = self._client_getter().execute(page_query, variable_values={"slug": slug})["page"]
        if page_raw is None:
            raise NotFoundError(f"Page not found: {slug}")
        return Page.model_validate(_standardize_page(page_raw))

    def get_posts_by_tag(self, tag: str, lang: str) -> list[Post]:
        """Retrieve posts filtered by tag and language.

        Args:
            tag: Tag name to filter by
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            List of Post objects
        """
        post = gql("""
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
            """)
        raw_posts = self._client_getter().execute(post, variable_values={"tag": tag, "lang": lang})[
            "posts"
        ]
        return [Post.model_validate(_standardize_post_by_tag(p)) for p in raw_posts]

    def add_comment(self, author_name: str, comment: str, post_slug: str) -> None:
        """Add a new comment to a post.

        Args:
            author_name: Name of the comment author
            comment: Comment text content
            post_slug: URL-friendly identifier of the post
        """
        add_comment = gql("""
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
            """)
        self._client_getter().execute(
            add_comment,
            variable_values={
                "author": author_name,
                "comment": comment,
                "slug": post_slug,
            },
        )

    def get_site_settings(self) -> SiteSettings:
        """Retrieve branding and description settings for the app.

        Returns:
            The app's site settings.
        """
        return self._site_config.get_site_settings()

    @override
    def get_blog_meta(self, lang: str) -> PageMeta:
        """Retrieve the blog index's title and description for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            The blog meta
        """
        return self._site_config.get_blog_meta(lang)

    @override
    def get_footer(self, lang: str) -> Footer:
        """Retrieve the site-wide footer for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl')

        Returns:
            The footer
        """
        return self._site_config.get_footer(lang)

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
        return self._plugin_config.get_all()

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
