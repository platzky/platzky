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

    def test_added_comment_is_in_every_read_of_the_post(self, repository: JsonBlogRepository):
        repository.posts.add_comment("Bob", "hi", "post-1")

        posts = repository.posts
        assert [c.comment for c in posts.get("post-1").comments] == ["hi"]
        assert [c.comment for c in posts.get_all("en")[0].comments] == ["hi"]
        assert [c.comment for c in posts.get_by_tag("python", "en")[0].comments] == ["hi"]
        assert posts.get("post-2").comments == []

    def test_failed_comment_is_not_shown(self):
        repository = _repository(ReadOnlyStore(sample_data()))

        with pytest.raises(ReadOnlyStorageError):
            repository.posts.add_comment("Bob", "hi", "post-1")

        assert repository.posts.get("post-1").comments == []

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

    def test_post_without_tags_has_empty_tags(self):
        data = sample_data()
        del data["blog"]["posts"][0]["tags"]
        repository = _repository(MemoryStore(data))
        assert repository.posts.get("post-1").tags == []

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

    def test_get_all_treats_missing_pages_as_empty(self):
        repository = _repository(MemoryStore({"blog": {}}))
        assert repository.pages.get_all("en") == []


class TestMeta:
    def test_missing_blog_meta_is_empty(self):
        assert _repository(MemoryStore({"blog": {}})).get_meta("en") == PageMeta()

    @pytest.mark.parametrize(
        "meta",
        [
            {"en": {"unknown": "x"}},
            {"en": {"title": None}},
            {"en": None},
        ],
    )
    def test_invalid_blog_meta_is_rejected(self, meta: object):
        with pytest.raises(InvalidDataError, match=r"blog\.meta"):
            _repository(MemoryStore({"blog": {"meta": meta}}))


class TestContentIsValidatedWhenLoaded:
    @pytest.mark.parametrize("section", ["posts", "pages"])
    @pytest.mark.parametrize(
        ("change", "problem"),
        [
            (
                {"language": None},
                "blog.{section}.{position}.language: Input should be a valid string",
            ),
            ({"date": "01-01-2024"}, "blog.{section}.{position}.date: "),
            ({"tags": None}, "blog.{section}.{position}.tags: Input should be a valid list"),
            (
                {"excerpt": None},
                "blog.{section}.{position}.excerpt: Input should be a valid string",
            ),
            (
                {"css": "</style><script>alert(1)</script>"},
                "blog.{section}.{position}.css: Value error, "
                "css must not contain a '</style' sequence",
            ),
        ],
        ids=["language", "date", "null-tags", "excerpt", "css-breakout"],
    )
    def test_invalid_item_fails_loading_with_its_path(
        self, section: str, change: dict[str, Any], problem: str
    ):
        data = sample_data()
        position = len(data["blog"][section])
        item = {**data["blog"][section][0], "slug": "second", **change}
        data["blog"][section].append(item)

        with pytest.raises(InvalidDataError) as error:
            _repository(MemoryStore(data))

        assert str(error.value).startswith(problem.format(section=section, position=position))
        assert str(error.value).count("\n") == 0

    @pytest.mark.parametrize("section", ["posts", "pages"])
    @pytest.mark.parametrize("field", ["author", "excerpt", "language"])
    def test_item_missing_a_required_field_fails_loading_with_its_path(
        self, section: str, field: str
    ):
        data = sample_data()
        del data["blog"][section][0][field]

        with pytest.raises(InvalidDataError) as error:
            _repository(MemoryStore(data))

        assert str(error.value) == f"blog.{section}.0.{field}: Field required"

    def test_valid_content_with_a_date_loads(self):
        data = sample_data()
        data["blog"]["pages"][0]["date"] = "2024-01-01T00:00:00+00:00"

        repository = _repository(MemoryStore(data))

        assert repository.pages.get("page-1").date == datetime.datetime(
            2024, 1, 1, tzinfo=datetime.timezone.utc
        )


class TestCreation:
    def test_lists_every_problem_with_its_path(self):
        with pytest.raises(InvalidDataError) as error:
            _repository(
                MemoryStore({"blog": {"posts": None, "meta": {"pl": {"title": None}}, "x": 1}})
            )

        assert str(error.value).splitlines() == [
            "blog.posts: Input should be a valid tuple",
            "blog.meta.pl.title: Input should be a valid string",
            "blog.x: Extra inputs are not permitted",
        ]


class TestBlogSection:
    def test_missing_blog_section_is_an_empty_blog(self):
        repository = _repository(MemoryStore({}))

        assert repository.posts.get_all("en") == []
        assert repository.pages.get_all("en") == []
        assert repository.get_meta("en") == PageMeta()

    @pytest.mark.parametrize("content", [None, [], "text", 5])
    def test_blog_not_a_dict_raises_db_error(self, content: object):
        with pytest.raises(DBError):
            _repository(MemoryStore({"blog": content}))

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
