"""BlogStorage implementation backed by a GraphQL (Hygraph) CMS."""

from typing import Any, Callable

from gql import Client, gql

from platzky.db.exceptions import NotFoundError
from platzky.db.graphql_client import make_lazy_graphql_client
from platzky.models import Page, Post


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


class _GraphQLPostRepository:
    """Post repository backed by a GraphQL CMS."""

    def __init__(self, get_client: Callable[[], Client]) -> None:
        self._get_client = get_client

    def get(self, slug: str) -> Post:
        """Retrieve a single post by its slug.

        Args:
            slug: URL-friendly identifier for the post.

        Returns:
            The matching post.

        Raises:
            NotFoundError: If no post has this slug.
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

        post_raw = self._get_client().execute(post, variable_values={"slug": slug})["post"]
        if post_raw is None:
            raise NotFoundError(f"Post not found: {slug}")
        return Post.model_validate(_standardize_post(post_raw))

    def get_all(self, lang: str) -> list[Post]:
        """Retrieve all posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Posts in that language.
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
        raw_ql_posts = self._get_client().execute(all_posts, variable_values={"lang": lang})[
            "posts"
        ]

        return [Post.model_validate(_standardize_post(post)) for post in raw_ql_posts]

    def get_by_tag(self, tag: str, lang: str) -> list[Post]:
        """Retrieve posts filtered by tag and language.

        Args:
            tag: Tag name to filter by.
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Matching posts.
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
        raw_posts = self._get_client().execute(post, variable_values={"tag": tag, "lang": lang})[
            "posts"
        ]
        return [Post.model_validate(_standardize_post_by_tag(p)) for p in raw_posts]

    def add_comment(self, author_name: str, comment: str, post_slug: str) -> None:
        """Add a new comment to a post.

        Args:
            author_name: Name of the comment author.
            comment: Comment text content.
            post_slug: URL-friendly identifier of the post.
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
        self._get_client().execute(
            add_comment,
            variable_values={
                "author": author_name,
                "comment": comment,
                "slug": post_slug,
            },
        )


class _GraphQLPageRepository:
    """Page repository backed by a GraphQL CMS."""

    def __init__(self, get_client: Callable[[], Client]) -> None:
        self._get_client = get_client

    def get(self, slug: str) -> Page:
        """Retrieve a page by its slug.

        Args:
            slug: URL-friendly identifier for the page.

        Returns:
            The matching page.

        Raises:
            NotFoundError: If no page has this slug.
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
        page_raw = self._get_client().execute(page_query, variable_values={"slug": slug})["page"]
        if page_raw is None:
            raise NotFoundError(f"Page not found: {slug}")
        return Page.model_validate(_standardize_page(page_raw))


class GraphQLBlogStorage:
    """BlogStorage implementation backed by a GraphQL CMS.

    ``posts`` and ``pages`` share one lazily-built, per-thread client rather
    than each building their own -- see `graphql_client.make_lazy_graphql_client`.
    """

    def __init__(self, endpoint: str, token: str) -> None:
        """Build the shared client and the post/page repositories over it.

        Args:
            endpoint: GraphQL API endpoint URL.
            token: Authentication token for the API.
        """
        get_client = make_lazy_graphql_client(endpoint, token)
        self.posts = _GraphQLPostRepository(get_client)
        self.pages = _GraphQLPageRepository(get_client)
