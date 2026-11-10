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

from collections.abc import Sequence
from typing import Any

import pytest

from platzky.db.blog_repository import BlogRepository
from platzky.db.exceptions import NotFoundError
from platzky.models import Page, Post

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


class BlogRepositoryContract:
    def make_repository(
        self, posts: Sequence[dict[str, Any]] = (), pages: Sequence[dict[str, Any]] = ()
    ) -> BlogRepository:
        """Build a repository of one backend holding these posts and pages."""
        raise NotImplementedError

    def test_get_returns_every_field(self):
        repository = self.make_repository(posts=[_POST])

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

    def test_get_unknown_post_slug_raises_not_found(self):
        repository = self.make_repository()

        with pytest.raises(NotFoundError):
            repository.posts.get("missing")

    def test_get_all_returns_mapped_posts(self):
        repository = self.make_repository(posts=[_POST, {**_POST, "slug": "second"}])

        posts = repository.posts.get_all("en")

        assert [p.model_dump() for p in posts] == [
            Post.model_validate(_POST).model_dump(),
            Post.model_validate({**_POST, "slug": "second"}).model_dump(),
        ]

    def test_get_by_tag_returns_full_posts(self):
        repository = self.make_repository(posts=[_POST])

        posts = repository.posts.get_by_tag("python", "en")

        assert [p.model_dump() for p in posts] == [Post.model_validate(_POST).model_dump()]

    def test_add_comment_unknown_slug_raises_not_found(self):
        repository = self.make_repository()

        with pytest.raises(NotFoundError):
            repository.posts.add_comment("Bob", "Hi", "missing")

    def test_get_returns_mapped_page(self):
        repository = self.make_repository(pages=[_PAGE])

        page = repository.pages.get("about")

        assert page.model_dump() == Page.model_validate(_PAGE).model_dump()
        assert page.author == "Grace"
        assert page.language == "pl"
        assert page.coverImage.url == "/img/about.png"

    def test_get_unknown_page_slug_raises_not_found(self):
        repository = self.make_repository()

        with pytest.raises(NotFoundError):
            repository.pages.get("missing")

    def test_get_all_returns_mapped_pages(self):
        repository = self.make_repository(pages=[_PAGE, _OTHER_PAGE])

        pages = repository.pages.get_all("pl")

        assert [p.model_dump() for p in pages] == [
            Page.model_validate(_PAGE).model_dump(),
            Page.model_validate(_OTHER_PAGE).model_dump(),
        ]
