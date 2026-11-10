"""Blog repository implementation backed by MongoDB collections."""

import datetime
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError
from pymongo.collection import Collection
from typing_extensions import override

from platzky.db.blog_repository import BlogRepository, PageRepository, PostRepository
from platzky.db.exceptions import InvalidSiteContentError, NotFoundError
from platzky.models import Page, PageMeta, Post


def _meta_of(document: Mapping[str, Any]) -> PageMeta:
    """Return the meta a ``blog_meta`` document holds, without its ``_id``."""
    return PageMeta.model_validate({key: value for key, value in document.items() if key != "_id"})


class _MongoPostRepository(PostRepository):
    """Post repository backed by a MongoDB collection."""

    def __init__(self, posts: Collection[Any]) -> None:
        self._posts = posts

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
        post_doc = self._posts.find_one({"slug": slug})
        if post_doc is None:
            raise NotFoundError(f"Post with slug {slug} not found")
        return Post.model_validate(post_doc)

    @override
    def get_all(self, lang: str) -> list[Post]:
        """Retrieve all posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Posts in that language.
        """
        return [Post.model_validate(post) for post in self._posts.find({"language": lang})]

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
            Post.model_validate(post) for post in self._posts.find({"tags": tag, "language": lang})
        ]

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
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        comment_doc = {
            "author": str(author_name),
            "comment": str(comment),
            "date": now_utc,
        }

        result = self._posts.update_one({"slug": post_slug}, {"$push": {"comments": comment_doc}})
        if result.matched_count == 0:
            raise NotFoundError(f"Post with slug {post_slug} not found")


class _MongoPageRepository(PageRepository):
    """Page repository backed by a MongoDB collection."""

    def __init__(self, pages: Collection[Any]) -> None:
        self._pages = pages

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
        page_doc = self._pages.find_one({"slug": slug})
        if page_doc is None:
            raise NotFoundError(f"Page with slug {slug} not found")
        return Page.model_validate(page_doc)

    @override
    def get_all(self, lang: str) -> list[Page]:
        """Retrieve all pages for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Pages in that language.
        """
        return [Page.model_validate(page) for page in self._pages.find({"language": lang})]


class MongoBlogRepository(BlogRepository):
    """BlogRepository implementation backed by the posts, pages and blog meta collections.

    ``blog_meta`` holds one document per language, with the language code as ``_id``, and the
    fields ``title`` and ``description``.
    """

    def __init__(
        self, posts: Collection[Any], pages: Collection[Any], blog_meta: Collection[Any]
    ) -> None:
        """Build the post/page repositories over the shared collections.

        Args:
            posts: The database's ``posts`` collection.
            pages: The database's ``pages`` collection.
            blog_meta: The database's ``blog_meta`` collection.
        """
        self._blog_meta = blog_meta
        self._post_repository = _MongoPostRepository(posts)
        self._page_repository = _MongoPageRepository(pages)

    @property
    @override
    def posts(self) -> PostRepository:
        """Return the post repository."""
        return self._post_repository

    @property
    @override
    def pages(self) -> PageRepository:
        """Return the page repository."""
        return self._page_repository

    def validate(self) -> None:
        """Read the whole ``blog_meta`` collection once and validate every document.

        Raises:
            InvalidSiteContentError: If a document is invalid; the message names its ``_id``
                and lists every problem, one per line.
        """
        problems: list[str] = []
        for document in self._blog_meta.find():
            try:
                _meta_of(document)
            except ValidationError as error:
                problems.extend(
                    ".".join(["blog_meta", str(document["_id"]), *(str(p) for p in e["loc"])])
                    + f": {e['msg']}"
                    for e in error.errors()
                )
        if problems:
            raise InvalidSiteContentError("\n".join(problems))

    @override
    def get_meta(self, lang: str) -> PageMeta:
        """Retrieve the title and description of the blog index.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The blog index meta, empty if none is configured for the language.
        """
        return _meta_of(self._blog_meta.find_one({"_id": lang}) or {})
