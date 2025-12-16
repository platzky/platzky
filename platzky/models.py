import datetime

import humanize
from pydantic import BaseModel


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
        date: ISO 8601 formatted date string of when the comment was posted
    """

    author: str
    comment: str
    date: str  # TODO change its type to datetime

    @property
    def time_delta(self) -> str:
        """Calculate human-readable time since the comment was posted.

        Returns:
            Human-friendly time description (e.g., "2 hours ago", "3 days ago")
        """
        now = datetime.datetime.now()
        date = datetime.datetime.strptime(self.date.split(".")[0], "%Y-%m-%dT%H:%M:%S")
        return humanize.naturaltime(now - date)


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
        date: ISO 8601 formatted date string of when the post was published
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
    date: str

    def __lt__(self, other):
        """Compare posts by date for sorting.

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
