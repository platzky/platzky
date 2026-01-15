import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from platzky.models import Color, Image, Page, Post


def make_post(**overrides) -> Post:
    """Create a Post with sensible defaults, allowing specific overrides."""
    defaults: dict[str, Any] = {
        "author": "author",
        "slug": "slug",
        "title": "title",
        "contentInMarkdown": "content",
        "excerpt": "excerpt",
    }
    return Post(**{**defaults, **overrides})


def make_post_data(**overrides) -> dict[str, Any]:
    """Create Post data dict with sensible defaults for model_validate tests."""
    defaults: dict[str, Any] = {
        "author": "author",
        "slug": "slug",
        "title": "title",
        "contentInMarkdown": "content",
        "comments": [],
        "excerpt": "excerpt",
        "tags": [],
        "language": "en",
        "coverImage": Image(),
    }
    return {**defaults, **overrides}


class TestPostSorting:
    def test_posts_are_sorted_by_date(self):
        older_post = make_post(date=datetime.datetime(2021, 2, 19, tzinfo=datetime.timezone.utc))
        newer_post = make_post(date=datetime.datetime(2021, 2, 20, tzinfo=datetime.timezone.utc))

        assert older_post < newer_post

    def test_posts_cannot_be_compared_with_other_types(self):
        post = make_post(date=datetime.datetime(2021, 2, 19, tzinfo=datetime.timezone.utc))

        with pytest.raises(TypeError):
            _ = post < 1

    def test_post_with_date_sorted_before_post_without_date(self):
        """Posts with None dates are sorted last."""
        post_with_date = make_post(
            slug="slug1",
            date=datetime.datetime(2021, 2, 19, tzinfo=datetime.timezone.utc),
        )
        post_without_date = make_post(slug="slug2")

        assert post_without_date < post_with_date
        assert not (post_with_date < post_without_date)

    def test_posts_with_none_dates_are_equal_in_sorting(self):
        """Two posts with None dates are equal in sorting."""
        post1 = make_post(slug="slug1")
        post2 = make_post(slug="slug2")

        assert not (post1 < post2)
        assert not (post2 < post1)


class TestColorValidation:
    """Test Color validation using Pydantic Field constraints."""

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("r", 256),
            ("g", 256),
            ("b", 256),
            ("a", 256),
            ("r", -1),
            ("g", -1),
            ("b", -1),
            ("a", -1),
        ],
    )
    def test_invalid_color_values_rejected(self, field: str, value: int) -> None:
        with pytest.raises(ValidationError):
            Color(**{field: value})

    def test_valid_edge_case_values(self):
        Color(r=0, g=0, b=0, a=0)
        Color(r=255, g=255, b=255, a=255)
        Color(r=10, g=200, b=50, a=250)


class TestDatetimeParsing:
    """Test backward compatibility for datetime parsing.

    NOTE: These tests cover deprecated string date parsing (will be removed in v2.0.0).
    """

    def test_naive_datetime_uses_utc(self):
        """Naive datetimes are interpreted as UTC.

        Regression test for a bug where naive dates used server local timezone,
        causing non-deterministic behavior across different servers.
        """
        with pytest.warns(DeprecationWarning, match="Passing date as string"):
            post = Post.model_validate(make_post_data(date="2021-02-19T12:30:00"))

        assert post.date is not None
        assert post.date.tzinfo is not None
        assert post.date.tzinfo == datetime.timezone.utc
        assert post.date.utcoffset() == datetime.timedelta(0)

    @pytest.mark.parametrize(
        ("date_string", "expected_offset"),
        [
            ("2021-02-19T12:30:00.123456+05:30", datetime.timedelta(hours=5, minutes=30)),
            ("2021-02-19T12:30:00.123456-05:00", datetime.timedelta(hours=-5)),
            ("2021-02-19T12:30:00.123456Z", datetime.timedelta(0)),
        ],
    )
    def test_datetime_parsing_preserves_timezone_with_microseconds(
        self, date_string: str, expected_offset: datetime.timedelta
    ) -> None:
        """String parsing preserves timezone with microseconds.

        Regression test for a bug where splitting on '.' to remove microseconds
        would also strip timezone info.
        """
        with pytest.warns(DeprecationWarning, match="Passing date as string"):
            post = Post.model_validate(make_post_data(date=date_string))

        assert post.date is not None
        assert post.date.utcoffset() == expected_offset


class TestPostWithMinimalFields:
    """Test that Post/Page can be created with only required fields.

    Regression test for a bug where pages/posts required all fields
    (comments, tags, language, date) even though they should be optional.
    """

    def test_post_with_minimal_fields(self):
        post = make_post()

        assert post.author == "author"
        assert post.slug == "slug"
        assert post.title == "title"
        assert post.contentInMarkdown == "content"
        assert post.excerpt == "excerpt"
        assert post.language == "en"
        assert post.comments == []
        assert post.tags == []
        assert post.date is None
        assert post.coverImage.url == ""
        assert post.coverImage.alternateText == ""

    def test_page_with_minimal_fields(self):
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
