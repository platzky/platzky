"""BlogRepository implementation backed by a shared JSON document.

`JsonBlogRepository` is the JSON-family (`JsonStore`) implementation of the
`BlogRepository` protocol. It gets only a `JsonSection` of the shared document (see
`json_document`), the ``blog`` section (``posts``, ``pages``, ``meta``), and writes through
`JsonSection.edit()`. It sees no other part of the document.
"""

import datetime
import logging
from collections.abc import Mapping
from typing import Any

from typing_extensions import override

from platzky.db.blog_repository import BlogRepository, PageRepository, PostRepository
from platzky.db.exceptions import NotFoundError
from platzky.db.json_document import JsonSection
from platzky.db.validation import parse
from platzky.models import LanguageCode, Page, PageMeta, Post, ReadOnlyMapping, StrictModel

logger = logging.getLogger(__name__)


class BlogSection(StrictModel):
    """The ``blog`` section of a JSON document, as stored.

    Unknown keys and null values are errors. Posts and pages are checked one at a time when they
    are read, so only their being lists of objects is checked here.

    Attributes:
        posts: Raw blog posts; each is validated as a `Post` when it is read
        pages: Raw pages; each is validated as a `Page` when it is read
        meta: The blog index meta by language code
    """

    posts: tuple[Mapping[str, Any], ...] = ()
    pages: tuple[Mapping[str, Any], ...] = ()
    meta: ReadOnlyMapping[LanguageCode, PageMeta]


class _JsonPostRepository(PostRepository):
    """Post repository backed by a shared, in-memory document."""

    def __init__(self, section: JsonSection) -> None:
        self._section = section

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
        wanted_post = next(
            (post for post in self._section.get("posts", []) if post["slug"] == slug), None
        )
        if wanted_post is None:
            raise NotFoundError(f"Post with slug {slug} not found")
        return Post.model_validate(wanted_post)

    @override
    def get_all(self, lang: LanguageCode) -> list[Post]:
        """Retrieve all posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Posts in that language.
        """
        return [
            Post.model_validate(post)
            for post in self._section.get("posts", [])
            if post.get("language", "en") == lang
        ]

    @override
    def get_by_tag(self, tag: str, lang: LanguageCode) -> list[Post]:
        """Retrieve posts filtered by tag and language.

        Args:
            tag: Tag name to filter by.
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Matching posts.
        """
        return [
            Post.model_validate(post)
            for post in self._section.get("posts", [])
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
            with self._section.edit() as blog:
                post = next((p for p in blog.get("posts", []) if p["slug"] == post_slug), None)
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

    def __init__(self, section: JsonSection) -> None:
        self._section = section

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
        wanted_page = next(
            (page for page in self._section.get("pages", []) if page["slug"] == slug), None
        )
        if wanted_page is None:
            raise NotFoundError(f"Page with slug {slug} not found")
        return Page.model_validate(wanted_page)

    @override
    def get_all(self, lang: LanguageCode) -> list[Page]:
        """Retrieve all pages for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Pages in that language.
        """
        return [
            Page.model_validate(page)
            for page in self._section.get("pages", [])
            if page.get("language", "en") == lang
        ]


class JsonBlogRepository(BlogRepository):
    """BlogRepository implementation backed by a shared JSON document."""

    def __init__(self, section: JsonSection) -> None:
        """Validate the section and build the post/page repositories over it.

        Posts and pages are read from the section live, as comments change them; each is
        validated when it is read. The meta does not change after loading, so it is kept parsed.

        Args:
            section: The ``blog`` section of the shared document, the only part of it this
                repository sees.

        Raises:
            InvalidDataError: If the section is invalid; the message lists every problem with
                its path, one per line.
        """
        self._meta = parse(BlogSection, section, section.name).meta
        self._posts = _JsonPostRepository(section)
        self._pages = _JsonPageRepository(section)

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
    def get_meta(self, lang: LanguageCode) -> PageMeta:
        """Retrieve the title and description of the blog index.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The blog index meta, empty if none is configured for the language.
        """
        return self._meta.get(lang, PageMeta())
