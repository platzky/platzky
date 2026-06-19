"""Pydantic models for blog posts, pages, comments, and CMS modules."""

import datetime
import functools
import re
from typing import Annotated

import humanize
from pydantic import AfterValidator, BaseModel, Field


def _ensure_utc(v: datetime.datetime) -> datetime.datetime:
    """Ensure a datetime is UTC-aware, converting naive datetimes to UTC."""
    if v.tzinfo is None:
        return v.replace(tzinfo=datetime.timezone.utc)
    return v


DateTimeField = Annotated[datetime.datetime, AfterValidator(_ensure_utc)]

_STYLE_CLOSE_RE = re.compile(r"</\s*style\b", re.IGNORECASE)


def _reject_style_breakout(css: str) -> str:
    """Reject CSS containing `</style`, which could break out of its wrapping tag.

    Content inside a <style> element is HTML "raw text" — browsers don't parse
    markup there except the literal closing tag. The `css` field is rendered with
    the `safe` filter (to preserve real CSS like `.a > .b`), so this guards the one
    sequence that could let stored content inject arbitrary HTML/script via the
    page's <head>. Raising here (rather than silently stripping it) means content
    with this pattern fails to load — see blog.py's handling of ValidationError for
    why that's preferable to rendering mutated content unexpectedly.
    """
    if _STYLE_CLOSE_RE.search(css):
        raise ValueError("css must not contain a '</style' sequence")
    return css


CssField = Annotated[str, AfterValidator(_reject_style_breakout)]


class CmsModule(BaseModel):
    """Represents a CMS module with basic metadata."""

    name: str
    description: str
    template: str
    slug: str


# CmsModuleGroup is also a CmsModule, but it contains other CmsModules
class CmsModuleGroup(CmsModule):
    """Represents a group of CMS modules, inheriting module properties."""

    modules: list[CmsModule] = []


class Image(BaseModel):
    """Represents an image with URL and alternate text.

    Attributes:
        url: URL path to the image resource
        alternateText: Descriptive text for accessibility and SEO
    """

    url: str = ""
    alternateText: str = ""


class MenuItem(BaseModel):
    """Represents a navigation menu item.

    Attributes:
        name: Display name of the menu item
        url: Target URL for the menu item link
    """

    name: str
    url: str


class Comment(BaseModel):
    """Represents a user comment on a blog post or page.

    Attributes:
        author: Name of the comment author
        comment: The comment text content
        date: Datetime when the comment was posted (timezone-aware recommended)
    """

    author: str
    comment: str
    date: DateTimeField

    @property
    def time_delta(self) -> str:
        """Calculate human-readable time since the comment was posted.

        Uses timezone-aware datetimes to ensure accurate time delta calculations.

        Returns:
            Human-friendly time description (e.g., "2 hours ago", "3 days ago")
        """
        # self.date is already a datetime object (parsed by field_validator)
        # Always use timezone-aware datetime for consistency
        now = datetime.datetime.now(datetime.timezone.utc)
        return humanize.naturaltime(now - self.date)


@functools.total_ordering
class Post(BaseModel):
    """Represents a blog post with metadata, content, and comments.

    Attributes:
        author: Name of the post author
        slug: URL-friendly unique identifier for the post
        title: Post title
        contentInMarkdown: Post content in Markdown format
        excerpt: Short summary or preview of the post
        coverImage: Cover image for the post
        language: Language code for the post content (defaults to 'en')
        comments: Optional list of comments on this post
        tags: Optional list of tags for categorization
        date: Optional datetime when the post was published (timezone-aware recommended)
        css: Optional CSS rendered inline in this post/page's own <head>, scoped to
            this content only — can target the masthead, hero blocks, paragraphs,
            or anything else on the page
    """

    author: str
    slug: str
    title: str
    contentInMarkdown: str
    excerpt: str
    coverImage: Image = Field(default_factory=Image)
    language: str = "en"
    comments: list[Comment] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    date: DateTimeField | None = None
    css: CssField = ""

    def __lt__(self, other: object) -> bool:
        """Compare posts by date for sorting.

        Uses datetime comparison to ensure robust and correct ordering.
        Posts without dates are treated as "less than" dated posts, meaning they
        appear last when using descending sort (reverse=True, newest-first) and
        first when using ascending sort.

        Args:
            other: Another Post instance to compare against

        Returns:
            True if this post's date is earlier than the other post's date,
            or NotImplemented if comparing with a non-Post object
        """
        if isinstance(other, Post):
            # Posts without dates are sorted last
            if self.date is None and other.date is None:
                return False
            if self.date is None:
                return True  # None is "less than" any date (sorted last)
            if other.date is None:
                return False
            return self.date < other.date
        return NotImplemented


Page = Post  # Page is an alias for Post (static pages use the same structure)


class Color(BaseModel):
    """Represents an RGBA color value.

    Attributes:
        r: Red component (0-255)
        g: Green component (0-255)
        b: Blue component (0-255)
        a: Alpha/transparency component (0-255, where 255 is fully opaque)
    """

    r: int = Field(default=0, ge=0, le=255, description="Red component (0-255)")
    g: int = Field(default=0, ge=0, le=255, description="Green component (0-255)")
    b: int = Field(default=0, ge=0, le=255, description="Blue component (0-255)")
    a: int = Field(
        default=255, ge=0, le=255, description="Alpha component (0-255, where 255 is fully opaque)"
    )
