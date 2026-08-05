"""Repository-shaped protocols for blog content: posts and pages.

Blog content only exists for apps that actually have a blog, unlike site
settings (branding, nav menu) or plugin config, both of which every app needs
regardless of whether it uses blog content — so this is kept separate from
site-wide and plugin storage.
"""

from typing import Protocol

from platzky.models import Page, Post


class PostRepository(Protocol):
    """Repository for blog posts."""

    def get(self, slug: str) -> Post:
        """Retrieve a single post by its slug.

        Args:
            slug: URL-friendly identifier for the post.

        Returns:
            The matching post.

        Raises:
            NotFoundError: If posts data is missing, or no post has this slug.
        """
        ...

    def get_all(self, lang: str) -> list[Post]:
        """Retrieve all posts for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Posts in that language.
        """
        ...

    def get_by_tag(self, tag: str, lang: str) -> list[Post]:
        """Retrieve posts filtered by tag and language.

        Args:
            tag: Tag name to filter by.
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Matching posts.
        """
        ...

    def add_comment(self, author_name: str, comment: str, post_slug: str) -> None:
        """Add a new comment to a post.

        Args:
            author_name: Name of the comment author.
            comment: Comment text content.
            post_slug: URL-friendly identifier of the post.

        Raises:
            NotFoundError: If no post has this slug.
            ReadOnlyStorageError: If the backend does not support writes.
        """
        ...


class PageRepository(Protocol):
    """Repository for static pages."""

    def get(self, slug: str) -> Page:
        """Retrieve a page by its slug.

        Args:
            slug: URL-friendly identifier for the page.

        Returns:
            The matching page.

        Raises:
            NotFoundError: If pages data is missing, or no page has this slug.
        """
        ...


class BlogStorage(Protocol):
    """Repository-shaped view over an app's blog content."""

    @property
    def posts(self) -> PostRepository:
        """Post repository."""
        ...

    @property
    def pages(self) -> PageRepository:
        """Page repository."""
        ...
