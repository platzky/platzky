from typing import cast
from unittest.mock import Mock, patch

import pytest

from platzky.db.blog_storage import BlogStorage
from platzky.db.exceptions import NotFoundError
from platzky.db.mongo_blog_storage import MongoBlogStorage
from platzky.models import Post


def _post_doc(slug: str = "post-1", title: str = "Post 1") -> dict[str, object]:
    return {
        "_id": "1",
        "title": title,
        "slug": slug,
        "content": "Content",
        "language": "en",
        "tags": ["tag1"],
        "comments": [],
        "author": "Test Author",
        "contentInMarkdown": "# Post",
        "excerpt": "Post excerpt",
        "coverImage": {"url": "/images/post.jpg"},
        "date": "2023-01-01T00:00:00",
    }


@pytest.fixture
def posts() -> Mock:
    return Mock()


@pytest.fixture
def pages() -> Mock:
    return Mock()


@pytest.fixture
def storage(posts: Mock, pages: Mock) -> MongoBlogStorage:
    return MongoBlogStorage(posts, pages)


class TestPosts:
    def test_get_returns_matching_post(self, storage: MongoBlogStorage, posts: Mock):
        posts.find_one.return_value = _post_doc()

        post = storage.posts.get("post-1")

        assert isinstance(post, Post)
        assert post.title == "Post 1"
        posts.find_one.assert_called_once_with({"slug": "post-1"})

    def test_get_raises_not_found_for_unknown_slug(self, storage: MongoBlogStorage, posts: Mock):
        posts.find_one.return_value = None

        with pytest.raises(NotFoundError, match="Post with slug non-existent not found"):
            storage.posts.get("non-existent")

    def test_get_all_filters_by_language(self, storage: MongoBlogStorage, posts: Mock):
        posts.find.return_value = [_post_doc()]

        result = storage.posts.get_all("en")

        assert [p.slug for p in result] == ["post-1"]
        posts.find.assert_called_once_with({"language": "en"})

    def test_get_by_tag_filters_by_tag_and_language(self, storage: MongoBlogStorage, posts: Mock):
        posts.find.return_value = [_post_doc("tagged", "Tagged Post")]

        result = storage.posts.get_by_tag("tag1", "en")

        assert [p.title for p in result] == ["Tagged Post"]
        posts.find.assert_called_once_with({"tags": "tag1", "language": "en"})

    def test_add_comment_pushes_comment_document(self, storage: MongoBlogStorage, posts: Mock):
        with patch("platzky.db.mongo_blog_storage.datetime.datetime") as mock_datetime:
            test_date = Mock()
            test_date.isoformat.return_value = "2023-01-01T12:00:00"
            mock_datetime.now.return_value = test_date

            storage.posts.add_comment("Test User", "Great post!", "post-1")

        expected_comment = {
            "author": "Test User",
            "comment": "Great post!",
            "date": "2023-01-01T12:00:00",
        }
        cast(Mock, posts.update_one).assert_called_once_with(
            {"slug": "post-1"}, {"$push": {"comments": expected_comment}}
        )

    def test_add_comment_raises_not_found_when_nothing_matched(
        self, storage: MongoBlogStorage, posts: Mock
    ):
        posts.update_one.return_value.matched_count = 0

        with pytest.raises(NotFoundError, match="Post with slug missing not found"):
            storage.posts.add_comment("Alice", "Hi", "missing")


class TestPages:
    def test_get_returns_matching_page(self, storage: MongoBlogStorage, pages: Mock):
        pages.find_one.return_value = _post_doc("page-1", "Page 1")

        page = storage.pages.get("page-1")

        assert page.title == "Page 1"
        pages.find_one.assert_called_once_with({"slug": "page-1"})

    def test_get_raises_not_found_for_unknown_slug(self, storage: MongoBlogStorage, pages: Mock):
        pages.find_one.return_value = None

        with pytest.raises(NotFoundError, match="Page with slug non-existent not found"):
            storage.pages.get("non-existent")

    def test_get_all_filters_by_language(self, storage: MongoBlogStorage, pages: Mock):
        pages.find.return_value = [_post_doc("about-tolkien", "About Tolkien")]

        result = storage.pages.get_all("en")

        assert [p.slug for p in result] == ["about-tolkien"]
        pages.find.assert_called_once_with({"language": "en"})


def test_mongo_blog_storage_satisfies_blog_storage_protocol(
    storage: MongoBlogStorage,
) -> None:
    """Structural check: pyright rejects this assignment if the shape drifts."""
    conforms: BlogStorage = storage
    assert conforms is storage
