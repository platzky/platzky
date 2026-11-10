"""BlogRepository implementation backed by a GraphQL (Hygraph) CMS."""

from typing import Any, Callable

from gql import Client, gql
from typing_extensions import override

from platzky.db.blog_repository import BlogRepository, PageRepository, PostRepository
from platzky.db.exceptions import NotFoundError
from platzky.models import Page, PageMeta, Post


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
        "author": (post.get("author") or {}).get("name") or "",
        "slug": post["slug"],
        "title": post["title"],
        "excerpt": post.get("excerpt") or "",
        "contentInMarkdown": (post.get("contentInRichText") or {}).get("html") or "",
        "comments": [_standardize_comment(comment) for comment in post["comments"]],
        "tags": post["tags"],
        "language": post["language"],
        "coverImage": {
            "url": (post.get("coverImage") or {}).get("image", {}).get("url", ""),
            "alternateText": (post.get("coverImage") or {}).get("alternateText") or "",
        },
        "date": post["date"],
        "css": post.get("css") or "",
    }


def _standardize_page(page: dict[str, Any]) -> dict[str, Any]:
    """Standardize page data structure from GraphQL response.

    Hygraph pages have no excerpt, date, tags or comments, so those take empty defaults.

    Args:
        page: Raw page data from GraphQL response

    Returns:
        Standardized page dictionary compatible with Page model
    """
    return {
        "author": (page.get("author") or {}).get("name") or "",
        "slug": page["slug"],
        "title": page["title"],
        "excerpt": "",
        "contentInMarkdown": page["contentInMarkdown"],
        "comments": [],
        "tags": [],
        "language": page["lang"],
        "coverImage": {
            "url": (page.get("coverImage") or {}).get("url", ""),
        },
        "date": None,
        "css": page.get("css") or "",
    }


class _GraphQLPostRepository(PostRepository):
    """Post repository backed by a GraphQL CMS."""

    def __init__(self, get_client: Callable[[], Client]) -> None:
        self._get_client = get_client

    @override
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
                    createdAt
                }
              }
            }
            """)

        post_raw = self._get_client().execute(post, variable_values={"slug": slug})["post"]
        if post_raw is None:
            raise NotFoundError(f"Post not found: {slug}")
        return Post.model_validate(_standardize_post(post_raw))

    @override
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
                date
                language
                title
                slug
                author {
                    name
                }
                contentInRichText {
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
                    createdAt
                }
              }
            }
            """)
        raw_ql_posts = self._get_client().execute(all_posts, variable_values={"lang": lang})[
            "posts"
        ]

        return [Post.model_validate(_standardize_post(post)) for post in raw_ql_posts]

    @override
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
                date
                language
                title
                slug
                author {
                    name
                }
                contentInRichText {
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
                    createdAt
                }
              }
            }
            """)
        raw_posts = self._get_client().execute(post, variable_values={"tag": tag, "lang": lang})[
            "posts"
        ]
        return [Post.model_validate(_standardize_post(p)) for p in raw_posts]

    @override
    def add_comment(self, author_name: str, comment: str, post_slug: str) -> None:
        """Add a new comment to a post.

        Args:
            author_name: Name of the comment author.
            comment: Comment text content.
            post_slug: URL-friendly identifier of the post.

        Raises:
            NotFoundError: If no post has this slug.
        """
        exists = gql("""
            query MyQuery($slug: String!) {
              post(where: {slug: $slug}, stage: PUBLISHED) {
                id
              }
            }
            """)
        client = self._get_client()
        # Checked up front: a ``connect`` to a missing post only yields an opaque CMS error.
        # Only published posts count, like ``get``; a post deleted between the two calls
        # still surfaces the CMS error.
        if client.execute(exists, variable_values={"slug": post_slug})["post"] is None:
            raise NotFoundError(f"Post not found: {post_slug}")
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
        client.execute(
            add_comment,
            variable_values={
                "author": author_name,
                "comment": comment,
                "slug": post_slug,
            },
        )


class _GraphQLPageRepository(PageRepository):
    """Page repository backed by a GraphQL CMS."""

    def __init__(self, get_client: Callable[[], Client]) -> None:
        self._get_client = get_client

    @override
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
                lang
                author {
                    name
                }
                coverImage {
                    url
                }
              }
            }
            """)
        page_raw = self._get_client().execute(page_query, variable_values={"slug": slug})["page"]
        if page_raw is None:
            raise NotFoundError(f"Page not found: {slug}")
        return Page.model_validate(_standardize_page(page_raw))

    @override
    def get_all(self, lang: str) -> list[Page]:
        """Retrieve all pages for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Pages in that language.
        """
        pages_query = gql("""
            query MyQuery ($lang: Lang!){
              pages(where: {lang: $lang}, stage: PUBLISHED) {
                slug
                title
                contentInMarkdown
                css
                lang
                author {
                    name
                }
                coverImage {
                    url
                }
              }
            }
            """)
        raw_pages = self._get_client().execute(pages_query, variable_values={"lang": lang})["pages"]
        return [Page.model_validate(_standardize_page(page)) for page in raw_pages]


class GraphQLBlogRepository(BlogRepository):
    """BlogRepository implementation backed by a GraphQL CMS.

    ``posts`` and ``pages`` share the one client source they are given -- see
    `graphql_client.make_graphql_client_getter`.
    """

    def __init__(self, get_client: Callable[[], Client]) -> None:
        """Build the post/page repositories over a shared client source.

        Args:
            get_client: Zero-argument callable returning the GraphQL client to
                use for the current thread.
        """
        self._get_client = get_client
        self._posts = _GraphQLPostRepository(get_client)
        self._pages = _GraphQLPageRepository(get_client)

    @property
    @override
    def posts(self) -> PostRepository:
        """Return the post repository."""
        return self._posts

    @property
    @override
    def pages(self) -> PageRepository:
        """Return the page repository."""
        return self._pages

    @override
    def get_meta(self, lang: str) -> PageMeta:
        """Retrieve the title and description of the blog index.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The blog index meta, empty if none is configured for the language. Fields an
            editor left unset (null in Hygraph) are empty.
        """
        meta_query = gql("""
            query BlogMeta($lang: Lang!) {
              blogMeta(where: {language: $lang}, stage: PUBLISHED) {
                title
                description
              }
            }
            """)
        raw_meta = (
            self._get_client().execute(meta_query, variable_values={"lang": lang})["blogMeta"] or {}
        )
        return PageMeta(
            title=raw_meta.get("title") or "", description=raw_meta.get("description") or ""
        )
