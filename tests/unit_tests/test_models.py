import pytest

from platzky.models import Color, Image, Post


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
        date="2021-02-19",  # type: ignore[arg-type]  # Testing backward compatibility with string dates
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
        date="2021-02-20",  # type: ignore[arg-type]  # Testing backward compatibility with string dates
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
        date="2021-02-19",  # type: ignore[arg-type]  # Testing backward compatibility with string dates
    )

    with pytest.raises(NotImplementedError):
        _ = post < 1


def test_color_values():
    # Test upper bounds (values > 255 should fail)
    with pytest.raises(ValueError):
        Color(r=256, g=0, b=0, a=0)

    with pytest.raises(ValueError):
        Color(r=0, g=256, b=0, a=0)

    with pytest.raises(ValueError):
        Color(r=0, g=0, b=256, a=0)

    with pytest.raises(ValueError):
        Color(r=0, g=0, b=0, a=256)

    # Test lower bounds (negative values should fail)
    with pytest.raises(ValueError):
        Color(r=-1, g=0, b=0, a=0)

    with pytest.raises(ValueError):
        Color(r=0, g=-1, b=0, a=0)

    with pytest.raises(ValueError):
        Color(r=0, g=0, b=-1, a=0)

    with pytest.raises(ValueError):
        Color(r=0, g=0, b=0, a=-1)

    # Test edge cases (0 and 255 should be valid)
    _ = Color(r=0, g=0, b=0, a=0)  # All minimum values
    _ = Color(r=255, g=255, b=255, a=255)  # All maximum values
    _ = Color(r=10, g=200, b=50, a=250)  # Valid values in range


def test_datetime_parsing_with_microseconds_and_timezone():
    """Test that datetime parsing preserves timezone when microseconds are present.

    This is a regression test for a critical bug where splitting on '.' to remove
    microseconds would also strip timezone information.
    """
    import datetime

    # Test positive timezone with microseconds
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
