from platzky.models import Post, Color, Image
import pytest


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
        date="2021-02-19",
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
        date="2021-02-20",
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
        date="2021-02-19",
    )

    with pytest.raises(NotImplementedError):
        _ = post < 1


def test_color_values():
    with pytest.raises(ValueError):
        Color(r=256, g=0, b=0, a=0)

    with pytest.raises(ValueError):
        Color(r=0, g=256, b=0, a=0)

    with pytest.raises(ValueError):
        Color(r=0, g=0, b=256, a=0)

    with pytest.raises(ValueError):
        Color(r=0, g=0, b=0, a=256)

    _ = Color(r=10, g=200, b=50, a=250)
