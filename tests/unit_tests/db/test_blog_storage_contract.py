"""Contract suite: every BlogStorage implementation behaves identically.

Parametrized over the three backends (Json, Mongo, GraphQL) so posts and pages
can't silently drift apart between independently-implemented backends. Each
backend gets a factory taking the same neutral `posts` / `pages` lists (the Json
document's shape) and translating them into what that backend stores or serves:
the Json document itself, an in-file fake Mongo collection that honours the
filters `MongoBlogStorage` actually sends (so assertions are meaningful rather
than echoing a mock), or a fake GraphQL client that answers each query the way
the CMS would.

Documented backend differences are encoded as explicit expectations, not
skipped: GraphQL pages carry no language so `pages.get_all` is always `[]`;
GraphQL `add_comment` is a remote mutation (its variables are asserted instead
of reading the comment back) and cannot know whether a slug exists, so it
cannot raise `NotFoundError`; GraphQL `get_by_tag` returns lightweight posts
(no author or content), so only slug, tags and language are compared there.
"""

import copy
import datetime
from dataclasses import dataclass
from typing import Any, Callable

import pytest
from gql import GraphQLRequest
from graphql import print_ast

from platzky.db.blog_storage import BlogStorage
from platzky.db.exceptions import NotFoundError
from platzky.db.graphql_blog_storage import GraphQLBlogStorage
from platzky.db.json_blog_storage import JsonBlogStorage
from platzky.db.json_document import JsonDocument
from platzky.db.json_stores import MemoryStore
from platzky.db.mongo_blog_storage import MongoBlogStorage

_POSTS = [
    {
        "slug": "hello",
        "author": "Ann",
        "title": "Hello",
        "contentInMarkdown": "hello body",
        "excerpt": "hello excerpt",
        "language": "en",
        "tags": ["python", "web"],
        "date": "2024-01-02T03:04:05+00:00",
    },
    {
        "slug": "second",
        "author": "Ann",
        "title": "Second",
        "contentInMarkdown": "second body",
        "excerpt": "second excerpt",
        "language": "en",
        "tags": ["web"],
        "date": "2024-02-02T03:04:05+00:00",
        "comments": [
            {"author": "Cat", "comment": "First!", "date": "2024-01-03T00:00:00+00:00"},
        ],
    },
    {
        "slug": "czesc",
        "author": "Jan",
        "title": "Cześć",
        "contentInMarkdown": "treść",
        "excerpt": "zajawka",
        "language": "pl",
        "tags": ["python"],
        "date": "2024-03-02T03:04:05+00:00",
    },
]

_PAGES = [
    {
        "slug": "about",
        "author": "Ann",
        "title": "About",
        "contentInMarkdown": "about body",
        "excerpt": "about excerpt",
        "language": "en",
    },
    {
        "slug": "o-nas",
        "author": "Jan",
        "title": "O nas",
        "contentInMarkdown": "o nas treść",
        "excerpt": "o nas zajawka",
        "language": "pl",
    },
]


def _json_storage(posts: list[dict[str, Any]], pages: list[dict[str, Any]]) -> BlogStorage:
    document = {"site_content": {"posts": copy.deepcopy(posts), "pages": copy.deepcopy(pages)}}
    return JsonBlogStorage(JsonDocument(MemoryStore(document)))


@dataclass
class UpdateResult:
    matched_count: int


class _FakeMongoCollection:
    """Minimal stand-in for the slice of `pymongo.Collection` MongoBlogStorage uses.

    Supports equality filters, where a list-valued document field matches when
    it contains the value (Mongo's semantics for `{"tags": "python"}`), plus
    `update_one` with `$push`.
    """

    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = copy.deepcopy(documents)

    @staticmethod
    def _matches(document: dict[str, Any], query: dict[str, Any]) -> bool:
        for field, wanted in query.items():
            actual = document.get(field)
            if isinstance(actual, list):
                if wanted not in actual:
                    return False
            elif actual != wanted:
                return False
        return True

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        return next((d for d in self._documents if self._matches(d, query)), None)

    def find(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        return [d for d in self._documents if self._matches(d, query)]

    def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> UpdateResult:
        document = self.find_one(query)
        if document is not None:
            for field, value in update["$push"].items():
                document.setdefault(field, []).append(value)
        return UpdateResult(matched_count=1 if document else 0)


def _mongo_storage(posts: list[dict[str, Any]], pages: list[dict[str, Any]]) -> BlogStorage:
    return MongoBlogStorage(_FakeMongoCollection(posts), _FakeMongoCollection(pages))  # type: ignore[arg-type]


class _FakeGraphQLClient:
    """Answers the queries GraphQLBlogStorage sends from the neutral fixture data.

    Responses use the CMS's shape (nested author, rich-text content, ...); the
    `where` filters of the real queries (slug, language, tags) are applied here.
    Mutations are recorded in `mutations` rather than applied.
    """

    def __init__(self, posts: list[dict[str, Any]], pages: list[dict[str, Any]]) -> None:
        self._posts = posts
        self._pages = pages
        self.mutations: list[dict[str, Any]] = []

    @staticmethod
    def _cms_post(post: dict[str, Any]) -> dict[str, Any]:
        return {
            "author": {"name": post["author"]},
            "slug": post["slug"],
            "title": post["title"],
            "excerpt": post["excerpt"],
            "contentInRichText": {"html": post["contentInMarkdown"]},
            "comments": [
                {"author": c["author"], "comment": c["comment"], "createdAt": c["date"]}
                for c in post.get("comments", [])
            ],
            "tags": post["tags"],
            "language": post["language"],
            "coverImage": None,
            "date": post["date"],
        }

    def execute(self, query: GraphQLRequest, variable_values: dict[str, Any]) -> dict[str, Any]:
        operation = print_ast(query.document)
        if "createComment" in operation:
            self.mutations.append(variable_values)
            return {"createComment": {"id": "1"}}
        if "page(" in operation:
            page = next((p for p in self._pages if p["slug"] == variable_values["slug"]), None)
            return {
                "page": (
                    {
                        "slug": page["slug"],
                        "title": page["title"],
                        "contentInMarkdown": page["contentInMarkdown"],
                    }
                    if page
                    else None
                )
            }
        if "post(" in operation:
            post = next((p for p in self._posts if p["slug"] == variable_values["slug"]), None)
            return {"post": self._cms_post(post) if post else None}
        matching = [
            self._cms_post(p)
            for p in self._posts
            if p["language"] == variable_values["lang"]
            and ("tag" not in variable_values or variable_values["tag"] in p["tags"])
        ]
        if "tag" in variable_values:
            # The by-tag query selects only these fields (no author, content, language).
            keep = ("tags", "title", "slug", "excerpt", "date", "coverImage")
            matching = [{k: v for k, v in post.items() if k in keep} for post in matching]
        return {"posts": matching}


def _graphql_storage(posts: list[dict[str, Any]], pages: list[dict[str, Any]]) -> BlogStorage:
    client = _FakeGraphQLClient(posts, pages)
    return GraphQLBlogStorage(lambda: client)  # type: ignore[arg-type,return-value]


StorageFactory = Callable[[list[dict[str, Any]], list[dict[str, Any]]], BlogStorage]


@pytest.fixture(
    params=[_json_storage, _mongo_storage, _graphql_storage],
    ids=["Json", "Mongo", "GraphQL"],
)
def make_storage(request: pytest.FixtureRequest) -> StorageFactory:
    return request.param


@pytest.fixture(params=[_json_storage, _mongo_storage], ids=["Json", "Mongo"])
def make_local_storage(request: pytest.FixtureRequest) -> StorageFactory:
    """Backends that store comments themselves and so can read them back."""
    return request.param


class TestPostRepositoryContract:
    def test_get_returns_the_post(self, make_storage: StorageFactory):
        storage = make_storage(_POSTS, _PAGES)

        post = storage.posts.get("hello")

        assert post.slug == "hello"
        assert post.author == "Ann"
        assert post.title == "Hello"
        assert post.contentInMarkdown == "hello body"
        assert post.excerpt == "hello excerpt"
        assert post.language == "en"
        assert post.tags == ["python", "web"]
        assert post.comments == []

    def test_get_returns_existing_comments_with_author_text_and_date(
        self, make_storage: StorageFactory
    ):
        storage = make_storage(_POSTS, _PAGES)

        comments = storage.posts.get("second").comments

        assert [(c.author, c.comment, c.date) for c in comments] == [
            ("Cat", "First!", datetime.datetime(2024, 1, 3, tzinfo=datetime.timezone.utc))
        ]

    def test_get_unknown_slug_raises_not_found(self, make_storage: StorageFactory):
        storage = make_storage(_POSTS, _PAGES)

        with pytest.raises(NotFoundError):
            storage.posts.get("missing")

    def test_get_all_returns_only_posts_in_that_language(self, make_storage: StorageFactory):
        storage = make_storage(_POSTS, _PAGES)

        english = storage.posts.get_all("en")
        polish = storage.posts.get_all("pl")

        assert {p.slug for p in english} == {"hello", "second"}
        assert {p.slug for p in polish} == {"czesc"}
        assert all(p.language == "en" for p in english)

    def test_get_all_returns_empty_list_for_language_without_posts(
        self, make_storage: StorageFactory
    ):
        storage = make_storage(_POSTS, _PAGES)

        assert storage.posts.get_all("de") == []

    def test_get_by_tag_filters_by_tag_and_language(self, make_storage: StorageFactory):
        storage = make_storage(_POSTS, _PAGES)

        posts = storage.posts.get_by_tag("web", "en")

        assert {p.slug for p in posts} == {"hello", "second"}
        assert all(p.language == "en" for p in posts)
        assert all("web" in p.tags for p in posts)

    def test_get_by_tag_excludes_other_languages(self, make_storage: StorageFactory):
        storage = make_storage(_POSTS, _PAGES)

        posts = storage.posts.get_by_tag("python", "pl")

        assert [p.slug for p in posts] == ["czesc"]
        assert posts[0].language == "pl"

    def test_get_by_tag_returns_empty_list_for_unknown_tag(self, make_storage: StorageFactory):
        storage = make_storage(_POSTS, _PAGES)

        assert storage.posts.get_by_tag("nope", "en") == []

    def test_add_comment_is_visible_on_get(self, make_local_storage: StorageFactory):
        storage = make_local_storage(_POSTS, _PAGES)

        storage.posts.add_comment("Bob", "Nice post", "hello")

        comments = storage.posts.get("hello").comments
        assert [(c.author, c.comment) for c in comments] == [("Bob", "Nice post")]
        assert storage.posts.get("czesc").comments == []

    def test_add_comment_appends_to_existing_comments(self, make_local_storage: StorageFactory):
        storage = make_local_storage(_POSTS, _PAGES)

        storage.posts.add_comment("Bob", "first", "hello")
        storage.posts.add_comment("Eve", "second", "hello")

        assert [c.comment for c in storage.posts.get("hello").comments] == ["first", "second"]

    def test_add_comment_to_unknown_slug_raises_not_found(self, make_local_storage: StorageFactory):
        storage = make_local_storage(_POSTS, _PAGES)

        with pytest.raises(NotFoundError):
            storage.posts.add_comment("Bob", "Nice post", "missing")


class TestGraphQLPostCommentContract:
    """GraphQL `add_comment` is a remote mutation, so it can't be read back here.

    The CMS resolves the slug server-side, so unlike Json/Mongo this backend
    cannot raise `NotFoundError` for an unknown slug; we assert the mutation
    variables the backend sends instead.
    """

    def test_add_comment_sends_mutation_with_author_comment_and_slug(self):
        client = _FakeGraphQLClient(_POSTS, _PAGES)
        storage = GraphQLBlogStorage(lambda: client)  # type: ignore[arg-type]

        storage.posts.add_comment("Bob", "Nice post", "hello")

        assert client.mutations == [{"author": "Bob", "comment": "Nice post", "slug": "hello"}]


class TestPageRepositoryContract:
    def test_get_returns_the_page(self, make_storage: StorageFactory):
        storage = make_storage(_POSTS, _PAGES)

        page = storage.pages.get("about")

        assert page.slug == "about"
        assert page.title == "About"
        assert page.contentInMarkdown == "about body"

    def test_get_unknown_slug_raises_not_found(self, make_storage: StorageFactory):
        storage = make_storage(_POSTS, _PAGES)

        with pytest.raises(NotFoundError):
            storage.pages.get("missing")

    def test_get_all_returns_only_pages_in_that_language(self, make_storage: StorageFactory):
        storage = make_storage(_POSTS, _PAGES)

        if make_storage is _graphql_storage:
            # GraphQL pages carry no language (translated through slugs), so it is
            # documented to always return an empty list.
            assert storage.pages.get_all("en") == []
            assert storage.pages.get_all("pl") == []
            return
        assert [p.slug for p in storage.pages.get_all("en")] == ["about"]
        assert [p.slug for p in storage.pages.get_all("pl")] == ["o-nas"]

    def test_get_all_returns_empty_list_for_language_without_pages(
        self, make_storage: StorageFactory
    ):
        storage = make_storage(_POSTS, _PAGES)

        assert storage.pages.get_all("de") == []
