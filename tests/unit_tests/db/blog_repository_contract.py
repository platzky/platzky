"""Contract suite every BlogRepository backend must satisfy.

Subclass `BlogRepositoryContract` in the backend's own test module (the class name
must start with `Test` there so pytest collects it) and override `make_repository`.
It takes neutral `posts` / `pages` data (the Json document's shape) and builds a
repository over whatever that backend stores. A remote backend's fake only maps
fields and never filters: what the server decides is tested in the backend's own
file through the query variables it is sent, so each test seeds exactly what should
come back.

A behaviour the backend cannot represent is opted out by overriding the test with
`@pytest.mark.skip(reason=...)`. This module is not named `test_*`, and the class not
`Test*`, so pytest only collects the tests through the subclasses.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

import pytest

from platzky.db.blog_repository import BlogRepository
from platzky.db.exceptions import NotFoundError
from platzky.models import Page, Post

POST = {
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
PAGE = {
    "slug": "about",
    "author": "Grace",
    "title": "About",
    "contentInMarkdown": "About us",
    "excerpt": "",
    "language": "pl",
    "css": "p { margin: 0; }",
    "coverImage": {"url": "/img/about.png"},
}
_OTHERPAGE = {**PAGE, "slug": "kontakt", "title": "Kontakt"}


class BlogRepositoryContract(ABC):
    @abstractmethod
    def make_repository(
        self, posts: Sequence[dict[str, Any]] = (), pages: Sequence[dict[str, Any]] = ()
    ) -> BlogRepository:
        """Build a repository of one backend holding these posts and pages."""

    def test_get_returns_every_field(self):
        repository = self.make_repository(posts=[POST])

        post = repository.posts.get("hello")

        assert post == Post.model_validate(POST)

    def test_get_unknown_post_slug_raises_not_found(self):
        repository = self.make_repository()

        with pytest.raises(NotFoundError):
            repository.posts.get("missing")

    def test_get_all_returns_mapped_posts(self):
        repository = self.make_repository(posts=[POST, {**POST, "slug": "second"}])

        posts = repository.posts.get_all("en")

        assert posts == [Post.model_validate(POST), Post.model_validate({**POST, "slug": "second"})]

    def test_get_by_tag_returns_full_posts(self):
        repository = self.make_repository(posts=[POST])

        posts = repository.posts.get_by_tag("python", "en")

        assert posts == [Post.model_validate(POST)]

    def test_add_comment_unknown_slug_raises_not_found(self):
        repository = self.make_repository()

        with pytest.raises(NotFoundError):
            repository.posts.add_comment("Bob", "Hi", "missing")

    def test_get_returns_mapped_page(self):
        repository = self.make_repository(pages=[PAGE])

        page = repository.pages.get("about")

        assert page == Page.model_validate(PAGE)

    def test_get_unknown_page_slug_raises_not_found(self):
        repository = self.make_repository()

        with pytest.raises(NotFoundError):
            repository.pages.get("missing")

    def test_get_all_returns_mapped_pages(self):
        repository = self.make_repository(pages=[PAGE, _OTHERPAGE])

        pages = repository.pages.get_all("pl")

        assert [p.model_dump() for p in pages] == [
            Page.model_validate(PAGE).model_dump(),
            Page.model_validate(_OTHERPAGE).model_dump(),
        ]
