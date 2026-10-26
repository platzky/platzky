import json
from pathlib import Path
from typing import Any

import pytest

from platzky.db.blog_storage import BlogStorage
from platzky.db.exceptions import DBError, NotFoundError, ReadOnlyStorageError
from platzky.db.json_blog_storage import JsonBlogStorage
from platzky.db.json_document import JsonDocument
from platzky.db.json_stores import FileStore, JsonStore, MemoryStore, ReadOnlyStore


def _storage(store: JsonStore) -> JsonBlogStorage:
    return JsonBlogStorage(JsonDocument(store))


def sample_data() -> dict[str, Any]:
    return {
        "site_content": {
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
def storage(store: JsonStore) -> JsonBlogStorage:
    return _storage(store)


class TestPosts:
    def test_get_returns_matching_post(self, storage: JsonBlogStorage):
        post = storage.posts.get("post-1")
        assert post.slug == "post-1"
        assert post.title == "Title"

    def test_get_raises_not_found_for_unknown_slug(self, storage: JsonBlogStorage):
        with pytest.raises(NotFoundError):
            storage.posts.get("missing")

    def test_get_raises_not_found_when_posts_key_missing(self):
        storage = _storage(MemoryStore({"site_content": {}}))
        with pytest.raises(NotFoundError):
            storage.posts.get("post-1")

    def test_get_all_filters_by_language(self, storage: JsonBlogStorage):
        posts = storage.posts.get_all("en")
        assert [p.slug for p in posts] == ["post-1"]

    def test_get_by_tag_filters_by_tag_and_language(self, storage: JsonBlogStorage):
        posts = storage.posts.get_by_tag("python", "en")
        assert [p.slug for p in posts] == ["post-1"]

    def test_get_by_tag_excludes_other_language(self, storage: JsonBlogStorage):
        assert storage.posts.get_by_tag("python", "pl") == []

    def test_add_comment_persists_and_is_visible_via_get(
        self, storage: JsonBlogStorage, store: JsonStore
    ):
        storage.posts.add_comment("Alice", "Nice post!", "post-1")
        post = storage.posts.get("post-1")
        assert len(post.comments) == 1
        assert post.comments[0].author == "Alice"
        assert post.comments[0].comment == "Nice post!"

        # A fresh storage re-loads from the store, so this verifies persistence
        # (the saved JSON for FileStore), not just the shared in-memory dict.
        reloaded = _storage(store).posts.get("post-1")
        assert [(c.author, c.comment) for c in reloaded.comments] == [("Alice", "Nice post!")]

    def test_null_posts_is_treated_as_missing(self):
        storage = _storage(MemoryStore({"site_content": {"posts": None}}))
        assert storage.posts.get_all("en") == []
        assert storage.posts.get_by_tag("python", "en") == []
        with pytest.raises(NotFoundError):
            storage.posts.get("post-1")

    def test_null_tags_is_treated_as_missing(self):
        data = sample_data()
        data["site_content"]["posts"][0]["tags"] = None
        storage = _storage(MemoryStore(data))
        assert storage.posts.get_by_tag("python", "en") == []

    def test_add_comment_raises_not_found_for_unknown_slug(self, storage: JsonBlogStorage):
        with pytest.raises(NotFoundError):
            storage.posts.add_comment("Alice", "Nice post!", "missing")

    def test_add_comment_rolls_back_on_save_failure(self):
        data = sample_data()
        storage = _storage(ReadOnlyStore(data))

        with pytest.raises(ReadOnlyStorageError):
            storage.posts.add_comment("Alice", "Nice post!", "post-1")

        assert data["site_content"]["posts"][0]["comments"] == []

    def test_add_comment_rollback_removes_comments_key_if_it_was_absent(self):
        data = sample_data()
        del data["site_content"]["posts"][0]["comments"]
        storage = _storage(ReadOnlyStore(data))

        with pytest.raises(ReadOnlyStorageError):
            storage.posts.add_comment("Alice", "Nice post!", "post-1")

        assert "comments" not in data["site_content"]["posts"][0]


class TestPages:
    def test_get_returns_matching_page(self, storage: JsonBlogStorage):
        page = storage.pages.get("page-1")
        assert page.slug == "page-1"

    def test_get_raises_not_found_for_unknown_slug(self, storage: JsonBlogStorage):
        with pytest.raises(NotFoundError):
            storage.pages.get("missing")

    def test_get_all_filters_by_language(self, storage: JsonBlogStorage):
        assert [p.slug for p in storage.pages.get_all("en")] == ["page-1"]
        assert storage.pages.get_all("de") == []

    def test_get_all_defaults_missing_language_to_en(self):
        data = sample_data()
        del data["site_content"]["pages"][0]["language"]
        storage = _storage(MemoryStore(data))
        assert [p.slug for p in storage.pages.get_all("en")] == ["page-1"]

    @pytest.mark.parametrize("site_content", [{}, {"pages": None}])
    def test_get_all_treats_missing_or_null_pages_as_empty(self, site_content: dict[str, Any]):
        storage = _storage(MemoryStore({"site_content": site_content}))
        assert storage.pages.get_all("en") == []

    def test_get_raises_not_found_when_pages_key_missing(self):
        storage = _storage(MemoryStore({"site_content": {}}))
        with pytest.raises(NotFoundError):
            storage.pages.get("page-1")


class TestSharedDocument:
    def test_site_content_missing_raises_db_error(self):
        storage = _storage(MemoryStore({}))
        with pytest.raises(DBError):
            storage.posts.get_all("en")

    @pytest.mark.parametrize("content", [None, [], "text", 5])
    def test_site_content_not_a_dict_raises_db_error(self, content: object):
        storage = _storage(MemoryStore({"site_content": content}))
        with pytest.raises(DBError):
            storage.posts.get_all("en")


def test_json_blog_storage_satisfies_blog_storage_protocol(
    storage: JsonBlogStorage,
) -> None:
    """Structural check: pyright rejects this assignment if the shape drifts."""
    conforms: BlogStorage = storage
    assert conforms is storage
