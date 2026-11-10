from collections.abc import Callable, Mapping, Sequence
from typing import Any
from unittest.mock import Mock, patch

import pytest

from platzky.db.blog_repository import BlogRepository
from platzky.db.mongo_blog_repository import MongoBlogRepository
from tests.unit_tests.db.blog_repository_contract import PAGE, POST, BlogRepositoryContract


class TestMongoBlogRepositoryContract(BlogRepositoryContract):
    """Collections are fakes that look documents up by slug (meta by ``_id``) and never filter."""

    def make_repository(
        self,
        posts: Sequence[dict[str, Any]] = (),
        pages: Sequence[dict[str, Any]] = (),
        blog_meta: Mapping[str, Mapping[str, str]] | None = None,
    ) -> BlogRepository:
        meta = Mock()
        meta.find_one.side_effect = _meta_lookup(blog_meta or {})
        return MongoBlogRepository(_collection(posts), _collection(pages), meta)


def _meta_lookup(blog_meta: Mapping[str, Mapping[str, str]]) -> Callable[[dict[str, str]], Any]:
    def find_one(query: dict[str, str]) -> dict[str, str] | None:
        lang = query["_id"]
        return {"_id": lang, **blog_meta[lang]} if lang in blog_meta else None

    return find_one


def _collection(documents: Sequence[dict[str, Any]]) -> Mock:
    collection = Mock()
    collection.find.return_value = list(documents)
    collection.find_one.return_value = (list(documents) or [None])[0]
    collection.update_one.return_value = Mock(matched_count=len(documents))
    return collection


class TestMongoBlogRepository:
    @pytest.fixture
    def posts(self) -> Mock:
        return Mock()

    @pytest.fixture
    def pages(self) -> Mock:
        return Mock()

    @pytest.fixture
    def blog_meta(self) -> Mock:
        return Mock()

    @pytest.fixture
    def blog(self, posts: Mock, pages: Mock, blog_meta: Mock) -> MongoBlogRepository:
        return MongoBlogRepository(posts, pages, blog_meta)

    def test_get_meta_queries_by_language_id(self, blog: MongoBlogRepository, blog_meta: Mock):
        blog_meta.find_one.return_value = None

        blog.get_meta("pl")

        blog_meta.find_one.assert_called_once_with({"_id": "pl"})

    def test_get_all_posts_queries_by_language(self, blog: MongoBlogRepository, posts: Mock):
        posts.find.return_value = []

        blog.posts.get_all("en")

        posts.find.assert_called_once_with({"language": "en"})

    def test_get_post_queries_by_slug(self, blog: MongoBlogRepository, posts: Mock):
        posts.find_one.return_value = POST

        blog.posts.get("hello")

        posts.find_one.assert_called_once_with({"slug": "hello"})

    def test_get_posts_by_tag_queries_by_tag_and_language(
        self, blog: MongoBlogRepository, posts: Mock
    ):
        posts.find.return_value = []

        blog.posts.get_by_tag("tag1", "en")

        posts.find.assert_called_once_with({"tags": "tag1", "language": "en"})

    def test_get_all_pages_queries_by_language(self, blog: MongoBlogRepository, pages: Mock):
        pages.find.return_value = []

        blog.pages.get_all("en")

        pages.find.assert_called_once_with({"language": "en"})

    def test_get_page_queries_by_slug(self, blog: MongoBlogRepository, pages: Mock):
        pages.find_one.return_value = PAGE

        blog.pages.get("about")

        pages.find_one.assert_called_once_with({"slug": "about"})

    def test_add_comment_pushes_a_utc_dated_comment(self, blog: MongoBlogRepository, posts: Mock):
        with patch("platzky.db.mongo_blog_repository.datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"

            blog.posts.add_comment("Test User", "Great post!", "post-1")

        posts.update_one.assert_called_once_with(
            {"slug": "post-1"},
            {
                "$push": {
                    "comments": {
                        "author": "Test User",
                        "comment": "Great post!",
                        "date": "2023-01-01T12:00:00",
                    }
                }
            },
        )
