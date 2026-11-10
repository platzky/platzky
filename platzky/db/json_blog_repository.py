"""BlogRepository implementation backed by a shared JSON document.

`JsonBlogRepository` is the JSON-family (`JsonStore`) implementation of the
`BlogRepository` protocol. It gets only a `JsonSection` of the shared document (see
`json_document`), the ``blog`` section (``posts``, ``pages``, ``meta``), and writes through
`JsonSection.edit()`. It sees no other part of the document.
"""

import datetime
import logging
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
)
from typing_extensions import override

from platzky.db.blog_repository import BlogRepository, PageRepository, PostRepository
from platzky.db.exceptions import InvalidDataError, NotFoundError, format_problems
from platzky.db.json_document import JsonSection
from platzky.models import Page, PageMeta, Post

logger = logging.getLogger(__name__)

_META = TypeAdapter(Mapping[str, PageMeta])


class BlogSection(BaseModel):
    """The ``blog`` section of a JSON document, as stored.

    Unknown keys and null values are errors. Posts and pages are checked one at a time when they
    are read, so only their being lists of objects is checked here.

    Attributes:
        posts: Blog posts
        pages: Pages
        meta: The blog index meta by language code
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    posts: tuple[dict[str, Any], ...] = ()
    pages: tuple[dict[str, Any], ...] = ()
    meta: Mapping[str, PageMeta] = Field(default_factory=lambda: MappingProxyType({}))

    @field_validator("meta", mode="after")
    @classmethod
    def _read_only(cls, value: Mapping[str, PageMeta]) -> Mapping[str, PageMeta]:
        return MappingProxyType(dict(value))


def _as_tuple(section_name: str, key: str, value: object) -> tuple[dict[str, Any], ...]:
    """Return the posts or pages a section holds, as a tuple.

    Raises:
        InvalidDataError: If the value is not a list (null included).
    """
    if not isinstance(value, list):
        raise InvalidDataError(f"{section_name}.{key}: Input should be a valid list")
    return tuple(value)


def _items(section: JsonSection, key: str) -> tuple[dict[str, Any], ...] | None:
    """Return the posts or pages the section holds, None if it has none.

    Raises:
        InvalidDataError: If the key is present but not a list (null included).
    """
    data = section.data
    return _as_tuple(section.name, key, data[key]) if key in data else None


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
            NotFoundError: If posts data is missing, or no post has this slug.
        """
        all_posts = _items(self._section, "posts")
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
            for post in _items(self._section, "posts") or ()
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
            for post in _items(self._section, "posts") or ()
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
                if "posts" not in blog:
                    raise NotFoundError("Posts data is missing")
                posts = _as_tuple(self._section.name, "posts", blog["posts"])
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
            NotFoundError: If pages data is missing, or no page has this slug.
        """
        pages = _items(self._section, "pages")
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
            for page in _items(self._section, "pages") or ()
            if page.get("language", "en") == lang
        ]


class JsonBlogRepository(BlogRepository):
    """BlogRepository implementation backed by a shared JSON document."""

    def __init__(self, section: JsonSection) -> None:
        """Build the post/page repositories over the blog section.

        Args:
            section: The ``blog`` section of the shared document, the only part of it this
                repository sees.
        """
        self._section = section
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
    def get_meta(self, lang: str) -> PageMeta:
        """Retrieve the title and description of the blog index.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The blog index meta, empty if none is configured for the language.

        Raises:
            InvalidDataError: If the stored blog meta is invalid.
        """
        try:
            meta = _META.validate_python(self._section.data.get("meta", {}))
        except ValidationError as error:
            raise InvalidDataError(format_problems(error, self._section.name, "meta")) from error
        return meta.get(lang, PageMeta())

    def validate(self) -> None:
        """Check the whole section against the blog format, e.g. when the application starts.

        Raises:
            InvalidDataError: If it is invalid; the message lists every problem with its
                path, one per line.
        """
        try:
            BlogSection.model_validate(self._section.data)
        except ValidationError as error:
            raise InvalidDataError(format_problems(error, self._section.name)) from error
