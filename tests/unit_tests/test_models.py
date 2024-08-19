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


# create test which check if color class can have values only between 0 and 255
def test_color_values():
    with pytest.raises(ValueError):
        Color(r=256, g=0, b=0, a=0)

    with pytest.raises(ValueError):
        Color(r=0, g=256, b=0, a=0)

    with pytest.raises(ValueError):
        Color(r=0, g=0, b=256, a=0)

    with pytest.raises(ValueError):
        Color(r=0, g=0, b=0, a=256)
