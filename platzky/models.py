import datetime
import warnings

import humanize
from pydantic import BaseModel, field_validator


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
    date: datetime.datetime

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
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

        if isinstance(v, str):
            # Emit deprecation warning for string dates
            warnings.warn(
                f"Passing date as string ('{v}') is deprecated. "
                "Please use datetime objects instead. "
                "String support will be removed in version 2.0.0.",
                DeprecationWarning,
                stacklevel=2,
            )

            date_str = v.split(".")[0]  # Remove microseconds if present
            has_timezone = "+" in v or v.endswith("Z")

            if has_timezone:
                # Parse timezone-aware datetime
                if v.endswith("Z"):
                    date_str_with_tz = date_str + "+00:00"
                else:
                    date_str_with_tz = v.split(".")[0]
                return datetime.datetime.fromisoformat(date_str_with_tz)
            else:
                # Legacy format: naive datetime - make timezone-aware
                try:
                    parsed = datetime.datetime.fromisoformat(date_str)
                    return parsed.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)
                except ValueError:
                    # Fallback: date-only format
                    parsed_date = datetime.date.fromisoformat(date_str)
                    return datetime.datetime.combine(parsed_date, datetime.time.min).replace(
                        tzinfo=datetime.datetime.now().astimezone().tzinfo
                    )

        return v

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
            now = datetime.datetime.now()

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
    date: datetime.datetime

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
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

        if isinstance(v, str):
            # Emit deprecation warning for string dates
            warnings.warn(
                f"Passing date as string ('{v}') is deprecated. "
                "Please use datetime objects instead. "
                "String support will be removed in version 2.0.0.",
                DeprecationWarning,
                stacklevel=2,
            )

            date_str = v.split(".")[0]  # Remove microseconds if present
            has_timezone = "+" in v or v.endswith("Z")

            if has_timezone:
                # Parse timezone-aware datetime
                if v.endswith("Z"):
                    date_str_with_tz = date_str + "+00:00"
                else:
                    date_str_with_tz = v.split(".")[0]
                return datetime.datetime.fromisoformat(date_str_with_tz)
            else:
                # Legacy format: naive datetime - make timezone-aware
                try:
                    parsed = datetime.datetime.fromisoformat(date_str)
                    return parsed.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)
                except ValueError:
                    # Fallback: date-only format
                    parsed_date = datetime.date.fromisoformat(date_str)
                    return datetime.datetime.combine(parsed_date, datetime.time.min).replace(
                        tzinfo=datetime.datetime.now().astimezone().tzinfo
                    )

        return v

    def __lt__(self, other):
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

    def __init__(self, r: int = 0, g: int = 0, b: int = 0, a: int = 255):
        """Initialize a Color with RGBA values.

        Args:
            r: Red component (0-255), defaults to 0
            g: Green component (0-255), defaults to 0
            b: Blue component (0-255), defaults to 0
            a: Alpha component (0-255), defaults to 255

        Raises:
            ValueError: If any component is outside the valid range (0-255)
        """
        if not (0 <= r <= 255):
            raise ValueError("r must be between 0 and 255")
        if not (0 <= g <= 255):
            raise ValueError("g must be between 0 and 255")
        if not (0 <= b <= 255):
            raise ValueError("b must be between 0 and 255")
        if not (0 <= a <= 255):
            raise ValueError("a must be between 0 and 255")
        super().__init__(r=r, g=g, b=b, a=a)

    r: int
    g: int
    b: int
    a: int
