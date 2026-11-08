"""Contract suite: every BlogRepository behaves identically.

Parametrized over every backend that implements it (so far Json, GraphQL). Each
backend gets a factory taking the same neutral `posts` / `pages` data (the Json
document's shape) and translating it into what that backend stores: the Json
document itself, or the answer Hygraph would give for the query under test. The
GraphQL mock only maps fields; it never filters, as what the server decides is
tested in the GraphQL repository's own file through the query variables it is sent;
so each test seeds exactly what should come back.
"""

from collections.abc import Sequence
from typing import Any, Protocol
from unittest.mock import Mock

import pytest
from gql import Client

from platzky.db.blog_repository import BlogRepository
from platzky.db.exceptions import NotFoundError
from platzky.db.graphql_blog_repository import GraphQLBlogRepository
from platzky.db.json_blog_repository import JsonBlogRepository
from platzky.db.json_document import JsonDocument
from platzky.db.json_stores import MemoryStore
from platzky.models import Page, Post


class BlogFactory(Protocol):
    def __call__(
        self, posts: Sequence[dict[str, Any]] = (), pages: Sequence[dict[str, Any]] = ()
    ) -> BlogRepository: ...


_POST = {
    "slug": "hello",
    "author": "Ada",
    "title": "Hello",
    "contentInMarkdown": "# Hello",
    "excerpt": "A greeting",
    "language": "en",
    "tags": ["python", "web"],
    "date": "2024-05-01T10:00:00+00:00",
    "css": "h1 { color: red; }",
    "coverImage": {"url": "/img/hello.png", "alternateText": "A hello banner"},
    "comments": [
        {"author": "Bob", "comment": "Nice", "date": "2024-05-02T08:30:00+00:00"},
        {"author": "Eve", "comment": "Agreed", "date": "2024-05-03T09:15:00+00:00"},
    ],
}
_PAGE = {
    "slug": "about",
    "author": "Grace",
    "title": "About",
    "contentInMarkdown": "About us",
    "excerpt": "",
    "language": "pl",
    "css": "p { margin: 0; }",
    "coverImage": {"url": "/img/about.png"},
}
_OTHER_PAGE = {**_PAGE, "slug": "kontakt", "title": "Kontakt"}


def _json_repository(
    posts: Sequence[dict[str, Any]] = (), pages: Sequence[dict[str, Any]] = ()
) -> BlogRepository:
    document = JsonDocument(
        MemoryStore({"site_content": {"posts": list(posts), "pages": list(pages)}})
    )
    return JsonBlogRepository(document)


def _hygraph_post(post: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": post["slug"],
        "title": post["title"],
        "author": {"name": post["author"]},
        "contentInRichText": {"html": post["contentInMarkdown"]},
        "excerpt": post["excerpt"],
        "language": post["language"],
        "tags": post["tags"],
        "date": post["date"],
        "css": post["css"],
        "coverImage": {
            "alternateText": post["coverImage"]["alternateText"],
            "image": {"url": post["coverImage"]["url"]},
        },
        "comments": [
            {"author": c["author"], "comment": c["comment"], "createdAt": c["date"]}
            for c in post["comments"]
        ],
    }


def _hygraph_page(page: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": page["slug"],
        "title": page["title"],
        "author": {"name": page["author"]},
        "contentInMarkdown": page["contentInMarkdown"],
        "lang": page["language"],
        "css": page["css"],
        "coverImage": {"url": page["coverImage"]["url"]},
    }


def _graphql_repository(
    posts: Sequence[dict[str, Any]] = (), pages: Sequence[dict[str, Any]] = ()
) -> BlogRepository:
    client = Mock(spec=Client)
    client.execute.return_value = {
        "post": next(map(_hygraph_post, posts), None),
        "posts": [_hygraph_post(post) for post in posts],
        "page": next(map(_hygraph_page, pages), None),
        "pages": [_hygraph_page(page) for page in pages],
    }
    return GraphQLBlogRepository(lambda: client)


@pytest.fixture(
    params=[_json_repository, _graphql_repository],
    ids=["Json", "GraphQL"],
)
def make_repository(request: pytest.FixtureRequest) -> BlogFactory:
    return request.param


class TestPostRepositoryContract:
    def test_get_returns_every_field(self, make_repository: BlogFactory):
        repository = make_repository(posts=[_POST])

        post = repository.posts.get("hello")

        assert post.model_dump() == Post.model_validate(_POST).model_dump()
        assert post.author == "Ada"
        assert post.language == "en"
        assert post.excerpt == "A greeting"
        assert post.css == "h1 { color: red; }"
        assert post.coverImage.url == "/img/hello.png"
        assert post.coverImage.alternateText == "A hello banner"
        assert [(c.author, c.comment) for c in post.comments] == [
            ("Bob", "Nice"),
            ("Eve", "Agreed"),
        ]

    def test_get_unknown_slug_raises_not_found(self, make_repository: BlogFactory):
        repository = make_repository()

        with pytest.raises(NotFoundError):
            repository.posts.get("missing")

    def test_get_all_returns_mapped_posts(self, make_repository: BlogFactory):
        repository = make_repository(posts=[_POST, {**_POST, "slug": "second"}])

        posts = repository.posts.get_all("en")

        assert [p.model_dump() for p in posts] == [
            Post.model_validate(_POST).model_dump(),
            Post.model_validate({**_POST, "slug": "second"}).model_dump(),
        ]

    def test_get_by_tag_returns_full_posts(self, make_repository: BlogFactory):
        repository = make_repository(posts=[_POST])

        posts = repository.posts.get_by_tag("python", "en")

        assert [p.model_dump() for p in posts] == [Post.model_validate(_POST).model_dump()]

    def test_add_comment_unknown_slug_raises_not_found(self, make_repository: BlogFactory):
        repository = make_repository()

        with pytest.raises(NotFoundError):
            repository.posts.add_comment("Bob", "Hi", "missing")


class TestPageRepositoryContract:
    def test_get_returns_mapped_page(self, make_repository: BlogFactory):
        repository = make_repository(pages=[_PAGE])

        page = repository.pages.get("about")

        assert page.model_dump() == Page.model_validate(_PAGE).model_dump()
        assert page.author == "Grace"
        assert page.language == "pl"
        assert page.coverImage.url == "/img/about.png"

    def test_get_unknown_slug_raises_not_found(self, make_repository: BlogFactory):
        repository = make_repository()

        with pytest.raises(NotFoundError):
            repository.pages.get("missing")

    def test_get_all_returns_mapped_pages(self, make_repository: BlogFactory):
        repository = make_repository(pages=[_PAGE, _OTHER_PAGE])

        pages = repository.pages.get_all("pl")

        assert [p.model_dump() for p in pages] == [
            Page.model_validate(_PAGE).model_dump(),
            Page.model_validate(_OTHER_PAGE).model_dump(),
        ]
