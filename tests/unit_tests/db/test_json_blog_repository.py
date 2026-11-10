import datetime
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from platzky.db.blog_repository import BlogRepository
from platzky.db.exceptions import (
    DBError,
    InvalidDataError,
    ReadOnlyStorageError,
)
from platzky.db.json_blog_repository import JsonBlogRepository
from platzky.db.json_document import JsonDocument, JsonSection
from platzky.db.json_stores import FileStore, JsonStore, MemoryStore, ReadOnlyStore
from platzky.models import PageMeta
from tests.unit_tests.db.blog_repository_contract import BlogRepositoryContract


def _repository(store: JsonStore) -> JsonBlogRepository:
    return JsonBlogRepository(JsonSection(JsonDocument(store), "blog"))


def sample_data() -> dict[str, Any]:
    return {
        "blog": {
            "posts": [
                {
                    "slug": "post-1",
                    "author": "Author",
                    "title": "Title",
                    "contentInMarkdown": "content",
                    "excerpt": "excerpt",
                    "language": "en",
                    "tags": ["python"],
                    "comments": [],
                },
                {
                    "slug": "post-2",
                    "author": "Author",
                    "title": "Title 2",
                    "contentInMarkdown": "content 2",
                    "excerpt": "excerpt 2",
                    "language": "pl",
                    "tags": [],
                    "comments": [],
                },
            ],
            "pages": [
                {
                    "slug": "page-1",
                    "author": "Author",
                    "title": "Page title",
                    "contentInMarkdown": "page content",
                    "excerpt": "page excerpt",
                    "language": "en",
                }
            ],
        },
    }


def _memory_store(data: dict[str, Any], _tmp_path: Path) -> JsonStore:
    return MemoryStore(data)


def _file_store(data: dict[str, Any], tmp_path: Path) -> JsonStore:
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data))
    return FileStore(str(path))


@pytest.fixture(params=[_memory_store, _file_store], ids=["MemoryStore", "FileStore"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> JsonStore:
    return request.param(sample_data(), tmp_path)


@pytest.fixture
def repository(store: JsonStore) -> JsonBlogRepository:
    return _repository(store)


class TestPosts:
    def test_get_all_filters_by_language(self, repository: JsonBlogRepository):
        posts = repository.posts.get_all("en")
        assert [p.slug for p in posts] == ["post-1"]

    def test_get_all_returns_empty_list_for_language_without_posts(
        self, repository: JsonBlogRepository
    ):
        assert repository.posts.get_all("de") == []

    def test_get_returns_existing_comments_with_author_text_and_date(self):
        data = sample_data()
        data["blog"]["posts"][0]["comments"] = [
            {"author": "Cat", "comment": "First!", "date": "2024-01-03T00:00:00+00:00"}
        ]
        repository = _repository(MemoryStore(data))

        comments = repository.posts.get("post-1").comments

        assert [(c.author, c.comment, c.date) for c in comments] == [
            ("Cat", "First!", datetime.datetime(2024, 1, 3, tzinfo=datetime.timezone.utc))
        ]

    def test_add_comment_appends_to_existing_comments(self, repository: JsonBlogRepository):
        repository.posts.add_comment("Bob", "first", "post-1")
        repository.posts.add_comment("Eve", "second", "post-1")

        assert [c.comment for c in repository.posts.get("post-1").comments] == ["first", "second"]
        assert repository.posts.get("post-2").comments == []

    def test_get_by_tag_filters_by_tag_and_language(self, repository: JsonBlogRepository):
        posts = repository.posts.get_by_tag("python", "en")
        assert [p.slug for p in posts] == ["post-1"]

    def test_get_by_tag_excludes_other_language(self, repository: JsonBlogRepository):
        assert repository.posts.get_by_tag("python", "pl") == []

    def test_add_comment_persists_and_is_visible_via_get(
        self, repository: JsonBlogRepository, store: JsonStore
    ):
        repository.posts.add_comment("Alice", "Nice post!", "post-1")
        post = repository.posts.get("post-1")
        assert len(post.comments) == 1
        assert post.comments[0].author == "Alice"
        assert post.comments[0].comment == "Nice post!"

        # A fresh repository re-loads from the store, so this verifies persistence
        # (the saved JSON for FileStore), not just the shared in-memory dict.
        reloaded = _repository(store).posts.get("post-1")
        assert [(c.author, c.comment) for c in reloaded.comments] == [("Alice", "Nice post!")]

    def test_null_posts_is_an_error(self):
        repository = _repository(MemoryStore({"blog": {"posts": None}}))
        with pytest.raises(InvalidDataError, match=r"blog\.posts"):
            repository.posts.get_all("en")
        with pytest.raises(InvalidDataError, match=r"blog\.posts"):
            repository.posts.get_by_tag("python", "en")
        with pytest.raises(InvalidDataError, match=r"blog\.posts"):
            repository.posts.get("post-1")
        with pytest.raises(InvalidDataError, match=r"blog\.posts"):
            repository.posts.add_comment("Alice", "Hi", "post-1")

    def test_null_tags_is_treated_as_missing(self):
        data = sample_data()
        data["blog"]["posts"][0]["tags"] = None
        repository = _repository(MemoryStore(data))
        assert repository.posts.get_by_tag("python", "en") == []

    def test_add_comment_rolls_back_on_save_failure(self):
        data = sample_data()
        repository = _repository(ReadOnlyStore(data))

        with pytest.raises(ReadOnlyStorageError):
            repository.posts.add_comment("Alice", "Nice post!", "post-1")

        assert data["blog"]["posts"][0]["comments"] == []

    def test_add_comment_rollback_removes_comments_key_if_it_was_absent(self):
        data = sample_data()
        del data["blog"]["posts"][0]["comments"]
        repository = _repository(ReadOnlyStore(data))

        with pytest.raises(ReadOnlyStorageError):
            repository.posts.add_comment("Alice", "Nice post!", "post-1")

        assert "comments" not in data["blog"]["posts"][0]


class TestPages:
    def test_get_all_filters_by_language(self, repository: JsonBlogRepository):
        assert [p.slug for p in repository.pages.get_all("en")] == ["page-1"]
        assert repository.pages.get_all("de") == []

    def test_get_all_defaults_missing_language_to_en(self):
        data = sample_data()
        del data["blog"]["pages"][0]["language"]
        repository = _repository(MemoryStore(data))
        assert [p.slug for p in repository.pages.get_all("en")] == ["page-1"]

    def test_get_all_treats_missing_pages_as_empty(self):
        repository = _repository(MemoryStore({"blog": {}}))
        assert repository.pages.get_all("en") == []

    def test_null_pages_is_an_error(self):
        repository = _repository(MemoryStore({"blog": {"pages": None}}))
        with pytest.raises(InvalidDataError, match=r"blog\.pages"):
            repository.pages.get_all("en")


class TestMeta:
    def test_missing_blog_meta_is_empty(self):
        assert _repository(MemoryStore({"blog": {}})).get_meta("en") == PageMeta()

    @pytest.mark.parametrize(
        "meta",
        [
            {"en": {"unknown": "x"}},
            {"en": {"title": None}},
            {"en": None},
            None,
            ["en"],
        ],
    )
    def test_invalid_blog_meta_is_rejected(self, meta: object):
        repository = _repository(MemoryStore({"blog": {"meta": meta}}))

        with pytest.raises(InvalidDataError, match=r"blog\.meta"):
            repository.get_meta("en")


class TestValidate:
    def test_lists_every_problem_with_its_path(self):
        repository = _repository(
            MemoryStore({"blog": {"posts": None, "meta": {"pl": {"title": None}}, "x": 1}})
        )

        with pytest.raises(InvalidDataError) as error:
            repository.validate()

        assert str(error.value).splitlines() == [
            "blog.posts: Input should be a valid tuple",
            "blog.meta.pl.title: Input should be a valid string",
            "blog.x: Extra inputs are not permitted",
        ]

    def test_accepts_a_missing_section(self):
        _repository(MemoryStore({})).validate()

    def test_reading_a_post_does_not_validate_the_rest_of_the_section(self):
        data = sample_data()
        data["blog"]["x"] = 1
        repository = _repository(MemoryStore(data))

        assert repository.posts.get("post-1").slug == "post-1"


class TestBlogSection:
    def test_missing_blog_section_is_an_empty_blog(self):
        repository = _repository(MemoryStore({}))

        assert repository.posts.get_all("en") == []
        assert repository.pages.get_all("en") == []
        assert repository.get_meta("en") == PageMeta()

    @pytest.mark.parametrize("content", [None, [], "text", 5])
    def test_blog_not_a_dict_raises_db_error(self, content: object):
        repository = _repository(MemoryStore({"blog": content}))
        with pytest.raises(DBError):
            repository.posts.get_all("en")

    def test_site_config_is_not_read(self):
        data = sample_data()
        data["site_config"] = {"posts": [{"slug": "not-a-blog-post"}]}
        repository = _repository(MemoryStore(data))

        assert [p.slug for p in repository.posts.get_all("en")] == ["post-1"]


def test_json_blog_repository_satisfies_blog_repository_protocol(
    repository: JsonBlogRepository,
) -> None:
    """Structural check: pyright rejects this assignment if the shape drifts."""
    conforms: BlogRepository = repository
    assert conforms is repository


class TestJsonBlogRepositoryContract(BlogRepositoryContract):
    def make_repository(
        self,
        posts: Sequence[dict[str, Any]] = (),
        pages: Sequence[dict[str, Any]] = (),
        blog_meta: Mapping[str, Mapping[str, str]] | None = None,
    ) -> BlogRepository:
        return _repository(
            MemoryStore(
                {
                    "blog": {
                        "posts": list(posts),
                        "pages": list(pages),
                        "meta": dict(blog_meta or {}),
                    }
                }
            )
        )
