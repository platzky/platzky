import datetime

import pytest
from pydantic import ValidationError

from platzky.models import Color, Image, Page, Post


def test_posts_are_sorted_by_date():
    older_post = Post(
        author="author",
        slug="slug",
        title="title",
        contentInMarkdown="content",
        comments=[],
        excerpt="excerpt",
        tags=[],
        language="en",
        coverImage=Image(),
        date=datetime.datetime(2021, 2, 19, tzinfo=datetime.timezone.utc),
    )

    newer_post = Post(
        author="author",
        slug="slug",
        title="title",
        contentInMarkdown="content",
        comments=[],
        excerpt="excerpt",
        tags=[],
        language="en",
        coverImage=Image(),
        date=datetime.datetime(2021, 2, 20, tzinfo=datetime.timezone.utc),
    )

    assert older_post < newer_post


def test_that_posts_cant_be_compared_with_other_types():
    post = Post(
        author="author",
        slug="slug",
        title="title",
        contentInMarkdown="content",
        comments=[],
        excerpt="excerpt",
        tags=[],
        language="en",
        coverImage=Image(),
        date=datetime.datetime(2021, 2, 19, tzinfo=datetime.timezone.utc),
    )

    with pytest.raises(TypeError):
        _ = post < 1


def test_color_values():
    """Test Color validation using Pydantic Field constraints."""
    # Test upper bounds (values > 255 should fail)
    with pytest.raises(ValidationError):
        Color(r=256, g=0, b=0, a=0)

    with pytest.raises(ValidationError):
        Color(r=0, g=256, b=0, a=0)

    with pytest.raises(ValidationError):
        Color(r=0, g=0, b=256, a=0)

    with pytest.raises(ValidationError):
        Color(r=0, g=0, b=0, a=256)

    # Test lower bounds (negative values should fail)
    with pytest.raises(ValidationError):
        Color(r=-1, g=0, b=0, a=0)

    with pytest.raises(ValidationError):
        Color(r=0, g=-1, b=0, a=0)

    with pytest.raises(ValidationError):
        Color(r=0, g=0, b=-1, a=0)

    with pytest.raises(ValidationError):
        Color(r=0, g=0, b=0, a=-1)

    # Test edge cases (0 and 255 should be valid)
    _ = Color(r=0, g=0, b=0, a=0)  # All minimum values
    _ = Color(r=255, g=255, b=255, a=255)  # All maximum values
    _ = Color(r=10, g=200, b=50, a=250)  # Valid values in range


def test_naive_datetime_uses_utc():
    """Test backward compatibility: naive datetimes are interpreted as UTC.

    This is a regression test for a critical bug where naive dates used server
    local timezone, causing non-deterministic behavior across different servers.

    NOTE: Tests deprecated string date parsing (will be removed in v2.0.0).
    """

    # Test naive datetime is interpreted as UTC
    # Expects TWO warnings: one for string, one for naive datetime
    with pytest.warns(DeprecationWarning, match="Passing date as string"):
        post = Post.model_validate(
            {
                "author": "author",
                "slug": "slug",
                "title": "title",
                "contentInMarkdown": "content",
                "comments": [],
                "excerpt": "excerpt",
                "tags": [],
                "language": "en",
                "coverImage": Image(),
                "date": "2021-02-19T12:30:00",  # Naive datetime (no timezone)
            }
        )

    # Verify the date is timezone-aware and in UTC
    assert post.date.tzinfo is not None
    assert post.date.tzinfo == datetime.timezone.utc
    assert post.date.utcoffset() == datetime.timedelta(0)  # UTC offset is 0


def test_datetime_parsing_with_microseconds_and_timezone():
    """Test backward compatibility: string parsing preserves timezone with microseconds.

    This is a regression test for a critical bug in the deprecated string parsing
    where splitting on '.' to remove microseconds would also strip timezone info.

    NOTE: Tests deprecated string date parsing (will be removed in v2.0.0).
    """

    # Test positive timezone with microseconds
    with pytest.warns(DeprecationWarning, match="Passing date as string"):
        post = Post.model_validate(
            {
                "author": "author",
                "slug": "slug",
                "title": "title",
                "contentInMarkdown": "content",
                "comments": [],
                "excerpt": "excerpt",
                "tags": [],
                "language": "en",
                "coverImage": Image(),
                "date": "2021-02-19T12:30:00.123456+05:30",
            }
        )
    # Verify timezone is preserved (UTC+5:30 = offset of 19800 seconds)
    assert post.date.utcoffset() == datetime.timedelta(hours=5, minutes=30)

    # Test negative timezone with microseconds
    with pytest.warns(DeprecationWarning, match="Passing date as string"):
        post_negative = Post.model_validate(
            {
                "author": "author",
                "slug": "slug",
                "title": "title",
                "contentInMarkdown": "content",
                "comments": [],
                "excerpt": "excerpt",
                "tags": [],
                "language": "en",
                "coverImage": Image(),
                "date": "2021-02-19T12:30:00.123456-05:00",
            }
        )
    # Verify negative timezone is preserved (UTC-5:00 = offset of -18000 seconds)
    assert post_negative.date.utcoffset() == datetime.timedelta(hours=-5)

    # Test Z suffix with microseconds
    with pytest.warns(DeprecationWarning, match="Passing date as string"):
        post_z = Post.model_validate(
            {
                "author": "author",
                "slug": "slug",
                "title": "title",
                "contentInMarkdown": "content",
                "comments": [],
                "excerpt": "excerpt",
                "tags": [],
                "language": "en",
                "coverImage": Image(),
                "date": "2021-02-19T12:30:00.123456Z",
            }
        )
    # Verify Z is converted to UTC (offset of 0)
    assert post_z.date.utcoffset() == datetime.timedelta(0)


def test_post_with_minimal_fields():
    """Test that Post can be created with only required fields.

    This is a regression test for a bug where pages/posts required all fields
    (comments, tags, language, date) even though they should be optional.
    """
    post = Post(
        author="author",
        slug="slug",
        title="title",
        contentInMarkdown="content",
        excerpt="excerpt",
    )

    assert post.author == "author"
    assert post.slug == "slug"
    assert post.title == "title"
    assert post.contentInMarkdown == "content"
    assert post.excerpt == "excerpt"
    # Check defaults
    assert post.language == "en"
    assert post.comments == []
    assert post.tags == []
    assert post.date is None
    assert post.coverImage.url == ""
    assert post.coverImage.alternateText == ""


def test_page_with_minimal_fields():
    """Test that Page can be created with only required fields.

    This is a regression test for a bug where pages required all Post fields
    (comments, tags, language, date) even though they should be optional for pages.
    """
    page = Page(
        author="author",
        slug="about",
        title="About Us",
        contentInMarkdown="# About\n\nWelcome to our site.",
        excerpt="About page",
    )

    assert page.title == "About Us"
    assert page.slug == "about"
    assert page.language == "en"
    assert page.comments == []
    assert page.tags == []
    assert page.date is None


def test_post_sorting_with_none_dates():
    """Test that posts with None dates are sorted last."""
    post_with_date = Post(
        author="author",
        slug="slug1",
        title="Post with date",
        contentInMarkdown="content",
        excerpt="excerpt",
        date=datetime.datetime(2021, 2, 19, tzinfo=datetime.timezone.utc),
    )

    post_without_date = Post(
        author="author",
        slug="slug2",
        title="Post without date",
        contentInMarkdown="content",
        excerpt="excerpt",
    )

    # Post without date should be "less than" post with date (sorted last)
    assert post_without_date < post_with_date
    assert not (post_with_date < post_without_date)


def test_post_sorting_both_none_dates():
    """Test that two posts with None dates are equal in sorting."""
    post1 = Post(
        author="author",
        slug="slug1",
        title="Post 1",
        contentInMarkdown="content",
        excerpt="excerpt",
    )

    post2 = Post(
        author="author",
        slug="slug2",
        title="Post 2",
        contentInMarkdown="content",
        excerpt="excerpt",
    )

    # Neither should be less than the other
    assert not (post1 < post2)
    assert not (post2 < post1)
