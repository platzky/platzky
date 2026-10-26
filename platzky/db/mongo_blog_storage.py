"""BlogStorage implementation backed by MongoDB collections."""

import datetime
from typing import Any

from pymongo.collection import Collection

from platzky.db.exceptions import NotFoundError
from platzky.models import Page, Post


class _MongoPostRepository:
    """Post repository backed by a MongoDB collection."""

    def __init__(self, posts: Collection[Any]) -> None:
        self._posts = posts

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

    def get_all(self, lang: str) -> list[Post]:
        """Retrieve all posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Posts in that language.
        """
        return [Post.model_validate(post) for post in self._posts.find({"language": lang})]

    def get_by_tag(self, tag: str, lang: str) -> list[Post]:
        """Retrieve posts filtered by tag and language.

        Args:
            tag: Tag name to filter by.
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Matching posts.
        """
        posts_cursor = self._posts.find({"tags": tag, "language": lang})
        return [Post.model_validate(post) for post in posts_cursor]

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


class _MongoPageRepository:
    """Page repository backed by a MongoDB collection."""

    def __init__(self, pages: Collection[Any]) -> None:
        self._pages = pages

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

    def get_all(self, lang: str) -> list[Page]:
        """Retrieve all pages for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Pages in that language.
        """
        return [Page.model_validate(page) for page in self._pages.find({"language": lang})]


class MongoBlogStorage:
    """BlogStorage implementation backed by MongoDB collections."""

    def __init__(self, posts: Collection[Any], pages: Collection[Any]) -> None:
        """Build the post/page repositories over their collections.

        Args:
            posts: The database's ``posts`` collection.
            pages: The database's ``pages`` collection.
        """
        self.posts = _MongoPostRepository(posts)
        self.pages = _MongoPageRepository(pages)
