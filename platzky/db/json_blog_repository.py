"""BlogRepository implementation backed by a shared JSON document.

`JsonBlogRepository` is the JSON-family (`JsonStore`) implementation of the
`BlogRepository` protocol. It operates on a `JsonDocument` shared with the other
JSON repositories (see `json_document` for why the dict is shared) and writes
through `JsonDocument.edit()`.
"""

import datetime
import logging
from collections.abc import Mapping

from pydantic import TypeAdapter, ValidationError
from typing_extensions import override

from platzky.db.blog_repository import BlogRepository, PageRepository, PostRepository
from platzky.db.exceptions import InvalidSiteContentError, NotFoundError
from platzky.db.json_document import JsonDocument, get_site_content
from platzky.models import Page, PageMeta, Post

logger = logging.getLogger(__name__)

_BLOG_META = TypeAdapter(dict[str, PageMeta])


def parse_blog_meta(blog_meta: object) -> Mapping[str, PageMeta]:
    """Validate the ``blog_meta`` key of the site content, e.g. when the application starts.

    Args:
        blog_meta: The stored value: the blog index meta by language code. Null is an error.

    Returns:
        The blog index meta by language code.

    Raises:
        InvalidSiteContentError: If it is invalid; the message lists every problem with its
            path, one per line.
    """
    try:
        return _BLOG_META.validate_python(blog_meta)
    except ValidationError as error:
        raise InvalidSiteContentError(
            "\n".join(
                ".".join(["site_content", "blog_meta", *(str(part) for part in problem["loc"])])
                + f": {problem['msg']}"
                for problem in error.errors()
            )
        ) from error


class _JsonPostRepository(PostRepository):
    """Post repository backed by a shared, in-memory document."""

    def __init__(self, document: JsonDocument) -> None:
        self._document = document

    @override
    def get(self, slug: str) -> Post:
        """Retrieve a single post by its slug.

        Args:
            slug: URL-friendly identifier for the post.

        Returns:
            The matching post.

        Raises:
            NotFoundError: If posts data is missing, or no post has this slug.
        """
        all_posts = get_site_content(self._document.data).get("posts")
        if all_posts is None:
            raise NotFoundError("Posts data is missing")
        wanted_post = next((post for post in all_posts if post["slug"] == slug), None)
        if wanted_post is None:
            raise NotFoundError(f"Post with slug {slug} not found")
        return Post.model_validate(wanted_post)

    @override
    def get_all(self, lang: str) -> list[Post]:
        """Retrieve all posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Posts in that language.
        """
        return [
            Post.model_validate(post)
            for post in get_site_content(self._document.data).get("posts") or ()
            if post.get("language", "en") == lang
        ]

    @override
    def get_by_tag(self, tag: str, lang: str) -> list[Post]:
        """Retrieve posts filtered by tag and language.

        Args:
            tag: Tag name to filter by.
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Matching posts.
        """
        return [
            Post.model_validate(post)
            for post in get_site_content(self._document.data).get("posts") or ()
            if tag in (post.get("tags") or ()) and post.get("language", "en") == lang
        ]

    @override
    def add_comment(self, author_name: str, comment: str, post_slug: str) -> None:
        """Add a new comment to a post.

        Store dates in UTC with timezone info for consistency with MongoDB backend.
        This ensures accurate time delta calculations regardless of server timezone.
        Legacy dates without timezone info are still supported for backward compatibility.

        Args:
            author_name: Name of the comment author.
            comment: Comment text content.
            post_slug: URL-friendly identifier of the post.

        Raises:
            NotFoundError: If no post has this slug.
            ReadOnlyStorageError: If the backend does not support writes.
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

        comment_data = {
            "author": str(author_name),
            "comment": str(comment),
            "date": now_utc,
        }

        try:
            with self._document.edit() as data:
                posts = get_site_content(data).get("posts")
                if posts is None:
                    raise NotFoundError("Posts data is missing")
                post = next((p for p in posts if p["slug"] == post_slug), None)
                if post is None:
                    raise NotFoundError(f"Post with slug {post_slug} not found")
                post.setdefault("comments", []).append(comment_data)
        except NotFoundError:
            raise
        except BaseException:
            logger.exception("Failed to persist comment for post '%s'", post_slug)
            raise


class _JsonPageRepository(PageRepository):
    """Page repository backed by a shared, in-memory document."""

    def __init__(self, document: JsonDocument) -> None:
        self._document = document

    @override
    def get(self, slug: str) -> Page:
        """Retrieve a page by its slug.

        Args:
            slug: URL-friendly identifier for the page.

        Returns:
            The matching page.

        Raises:
            NotFoundError: If pages data is missing, or no page has this slug.
        """
        pages = get_site_content(self._document.data).get("pages")
        if pages is None:
            raise NotFoundError("Pages data is missing")
        wanted_page = next((page for page in pages if page["slug"] == slug), None)
        if wanted_page is None:
            raise NotFoundError(f"Page with slug {slug} not found")
        return Page.model_validate(wanted_page)

    @override
    def get_all(self, lang: str) -> list[Page]:
        """Retrieve all pages for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Pages in that language.
        """
        return [
            Page.model_validate(page)
            for page in get_site_content(self._document.data).get("pages") or ()
            if page.get("language", "en") == lang
        ]


class JsonBlogRepository(BlogRepository):
    """BlogRepository implementation backed by a shared JSON document."""

    def __init__(self, document: JsonDocument) -> None:
        """Build the post/page repositories over the shared document.

        Args:
            document: The loaded document, shared with the other JSON
                repositories.
        """
        self._document = document
        self._posts = _JsonPostRepository(document)
        self._pages = _JsonPageRepository(document)

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
            The blog index meta, empty if none is configured for the language.

        Raises:
            InvalidSiteContentError: If the stored blog meta is invalid.
        """
        meta = parse_blog_meta(get_site_content(self._document.data).get("blog_meta", {}))
        return meta.get(lang, PageMeta())
