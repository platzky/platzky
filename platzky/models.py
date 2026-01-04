import datetime
import warnings
from typing import Annotated

import humanize
from pydantic import BaseModel, BeforeValidator, Field


def _parse_date_string(v: str | datetime.datetime) -> datetime.datetime:
    """Parse date string to datetime for backward compatibility.

    Handles string dates in various ISO 8601 formats for backward compatibility.
    Emits deprecation warning when parsing strings.

    In version 2.0.0, only datetime objects will be accepted.

    Args:
        v: Either a datetime object or an ISO 8601 date string

    Returns:
        Timezone-aware datetime object

    Raises:
        ValueError: If the date string cannot be parsed
    """
    if isinstance(v, datetime.datetime):
        return v  # Already a datetime object

    # v must be a string (based on type annotation)
    # Emit deprecation warning for string dates
    warnings.warn(
        f"Passing date as string ('{v}') is deprecated. "
        "Please use datetime objects instead. "
        "String support will be removed in version 2.0.0.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Check for timezone in the original string (before any manipulation)
    # Check for: +HH:MM, -HH:MM, or Z suffix
    time_part = v.split("T")[-1] if "T" in v else ""
    has_timezone = (
        v.endswith("Z")
        or "+" in time_part
        or ("-" in time_part and ":" in time_part.split("-")[-1])
    )

    # Normalize 'Z' suffix to '+00:00' for fromisoformat
    normalized = v.replace("Z", "+00:00") if v.endswith("Z") else v

    if has_timezone:
        # Parse timezone-aware datetime (handles microseconds automatically)
        return datetime.datetime.fromisoformat(normalized)
    else:
        # Legacy format: naive datetime - make timezone-aware using UTC
        # SECURITY FIX: Use UTC instead of server local timezone for predictability
        warnings.warn(
            f"Naive datetime '{v}' interpreted as UTC. "
            "Explicitly specify timezone in future versions for clarity.",
            DeprecationWarning,
            stacklevel=2,
        )
        try:
            parsed = datetime.datetime.fromisoformat(normalized)
            return parsed.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            # Fallback: date-only format
            parsed_date = datetime.date.fromisoformat(normalized)
            return datetime.datetime.combine(
                parsed_date, datetime.time.min, tzinfo=datetime.timezone.utc
            )


# Type alias for datetime fields that accept strings for backward compatibility
# Input: str | datetime.datetime
# Output (after validation): datetime.datetime
DateTimeField = Annotated[
    datetime.datetime,
    BeforeValidator(_parse_date_string),
    # This allows str at the type-checker level while ensuring datetime after validation
]


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
        if self.date.tzinfo is not None:
            # Timezone-aware datetime
            now = datetime.datetime.now(datetime.timezone.utc)
        else:
            # Naive datetime (shouldn't happen with the validator, but handle it)
            # Use naive datetime to avoid TypeError on subtraction
            now = datetime.datetime.now(datetime.timezone.utc)

        return humanize.naturaltime(now - self.date)


class Post(BaseModel):
    """Represents a blog post with metadata, content, and comments.

    Attributes:
        author: Name of the post author
        slug: URL-friendly unique identifier for the post
        title: Post title
        contentInMarkdown: Post content in Markdown format
        comments: List of comments on this post
        excerpt: Short summary or preview of the post
        tags: List of tags for categorization
        language: Language code for the post content
        coverImage: Cover image for the post
        date: Datetime when the post was published (timezone-aware recommended)
    """

    author: str
    slug: str
    title: str
    contentInMarkdown: str
    comments: list[Comment]
    excerpt: str
    tags: list[str]
    language: str
    coverImage: Image
    date: DateTimeField

    def __lt__(self, other: object) -> bool:
        """Compare posts by date for sorting.

        Uses datetime comparison to ensure robust and correct ordering.

        Args:
            other: Another Post instance to compare against

        Returns:
            True if this post's date is earlier than the other post's date

        Raises:
            NotImplementedError: If comparing with a non-Post object
        """
        if isinstance(other, Post):
            return self.date < other.date
        raise NotImplementedError("Posts can only be compared with other posts")


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
