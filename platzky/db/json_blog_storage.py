"""BlogStorage implementation backed by a shared JSON document.

`JsonBlogStorage` is the JSON-family (`JsonStore`) implementation of the
`BlogStorage` protocol. It operates on a `JsonDocument` shared with the other
JSON repositories (see `json_document` for why the dict is shared) and takes
the document's write lock for every write.
"""

import datetime
import logging

from platzky.db.exceptions import NotFoundError
from platzky.db.json_document import JsonDocument
from platzky.db.json_document import get_site_content as _site_content
from platzky.models import Page, Post

logger = logging.getLogger(__name__)


class _JsonPostRepository:
    """Post repository backed by a shared, in-memory document."""

    def __init__(self, document: JsonDocument) -> None:
        self._document = document

    def get(self, slug: str) -> Post:
        """Retrieve a single post by its slug.

        Args:
            slug: URL-friendly identifier for the post.

        Returns:
            The matching post.

        Raises:
            NotFoundError: If posts data is missing, or no post has this slug.
        """
        all_posts = _site_content(self._document.data).get("posts")
        if all_posts is None:
            raise NotFoundError("Posts data is missing")
        wanted_post = next((post for post in all_posts if post["slug"] == slug), None)
        if wanted_post is None:
            raise NotFoundError(f"Post with slug {slug} not found")
        return Post.model_validate(wanted_post)

    def get_all(self, lang: str) -> list[Post]:
        """Retrieve all posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Posts in that language.
        """
        return [
            Post.model_validate(post)
            for post in _site_content(self._document.data).get("posts") or ()
            if post.get("language", "en") == lang
        ]

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
            for post in _site_content(self._document.data).get("posts") or ()
            if tag in (post.get("tags") or ()) and post.get("language", "en") == lang
        ]

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

        with self._document.write_lock:
            posts = _site_content(self._document.data).get("posts")
            if posts is None:
                raise NotFoundError("Posts data is missing")
            post = next((p for p in posts if p["slug"] == post_slug), None)
            if post is None:
                raise NotFoundError(f"Post with slug {post_slug} not found")

            had_comments = "comments" in post
            comments = post.setdefault("comments", [])
            comments.append(comment_data)
            try:
                self._document.store.save(self._document.data)
            except BaseException:
                if had_comments:
                    comments.pop()
                else:
                    del post["comments"]
                logger.exception("Failed to persist comment for post '%s'", post_slug)
                raise


class _JsonPageRepository:
    """Page repository backed by a shared, in-memory document."""

    def __init__(self, document: JsonDocument) -> None:
        self._document = document

    def get(self, slug: str) -> Page:
        """Retrieve a page by its slug.

        Args:
            slug: URL-friendly identifier for the page.

        Returns:
            The matching page.

        Raises:
            NotFoundError: If pages data is missing, or no page has this slug.
        """
        pages = _site_content(self._document.data).get("pages")
        if pages is None:
            raise NotFoundError("Pages data is missing")
        wanted_page = next((page for page in pages if page["slug"] == slug), None)
        if wanted_page is None:
            raise NotFoundError(f"Page with slug {slug} not found")
        return Page.model_validate(wanted_page)

    def get_all(self, lang: str) -> list[Page]:
        """Retrieve all pages for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Pages in that language.
        """
        return [
            Page.model_validate(page)
            for page in _site_content(self._document.data).get("pages") or ()
            if page.get("language", "en") == lang
        ]


class JsonBlogStorage:
    """BlogStorage implementation backed by a shared JSON document."""

    def __init__(self, document: JsonDocument) -> None:
        """Build the post/page repositories over the shared document.

        Args:
            document: The loaded document, shared with the other JSON
                repositories.
        """
        self.posts = _JsonPostRepository(document)
        self.pages = _JsonPageRepository(document)
