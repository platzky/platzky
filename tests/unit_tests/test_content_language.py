from typing import Any

import pytest
from flask.testing import FlaskClient

from platzky.config import Config
from platzky.platzky import create_app_from_config

_LANGUAGES = {
    "en": {"name": "English", "flag": "gb", "country": "GB"},
    "pl": {"name": "Polski", "flag": "pl", "country": "PL"},
}


def _content(slug: str, text: str, language: str) -> dict[str, Any]:
    return {
        "title": f"title {text}",
        "slug": slug,
        "author": "author",
        "excerpt": "excerpt",
        "contentInMarkdown": text,
        "language": language,
        "date": "2021-02-19",
    }


def _client(kind: str, items: list[dict[str, Any]]) -> FlaskClient:
    """Build a client over a site whose posts or pages (by `kind`) are `items`."""
    config = Config.model_validate(
        {
            "APP_NAME": "testingApp",
            "SECRET_KEY": "secret",  # NOSONAR - hardcoded secret acceptable in tests
            "USE_WWW": False,
            "BLOG_PREFIX": "/blog",
            "DEFAULT_LANGUAGE": "en",
            "LANGUAGES": _LANGUAGES,
            "DB": {
                "TYPE": "json",
                "DATA": {"site_config": {}, "blog": {kind: items}},
            },
        }
    )
    app = create_app_from_config(config)
    app.config["WTF_CSRF_ENABLED"] = False
    return app.test_client()


# Where a post and a page are served, relative to the language's root.
_KINDS = pytest.mark.parametrize(
    ("kind", "path"), [("posts", "/blog/x"), ("pages", "/blog/page/x")], ids=["post", "page"]
)


@_KINDS
def test_content_is_served_under_its_own_language(kind: str, path: str):
    client = _client(kind, [_content("x", "Polski tekst", "pl")])

    response = client.get(f"/pl{path}")

    assert response.status_code == 200
    assert b"Polski tekst" in response.data


@_KINDS
def test_content_under_another_language_moves_to_its_own(kind: str, path: str):
    client = _client(kind, [_content("x", "Polski tekst", "pl")])

    response = client.get(path)

    assert response.status_code == 301
    assert response.location == f"http://localhost/pl{path}"


@_KINDS
def test_content_of_the_default_language_moves_to_it_from_another_one(kind: str, path: str):
    client = _client(kind, [_content("x", "English text", "en")])

    assert client.get(path).status_code == 200
    response = client.get(f"/pl{path}")
    assert response.status_code == 301
    assert response.location == f"http://localhost{path}"


@_KINDS
def test_content_in_a_language_the_site_does_not_serve_is_not_found(kind: str, path: str):
    client = _client(kind, [_content("x", "Deutscher Text", "de")])

    assert client.get(path).status_code == 404
    assert client.get(f"/pl{path}").status_code == 404


def test_a_comment_to_a_post_in_the_requests_language_is_stored():
    client = _client("posts", [_content("x", "Wpis", "pl")])

    accepted = client.post("/pl/blog/x", data={"author_name": "Ann", "comment": "Hello there"})

    assert accepted.status_code == 200
    assert b"Hello there" in client.get("/pl/blog/x").data


def test_a_comment_to_a_post_in_another_language_is_rejected_and_not_stored():
    client = _client("posts", [_content("x", "Wpis", "pl")])

    rejected = client.post("/blog/x", data={"author_name": "Ann", "comment": "Hello there"})

    assert rejected.status_code == 404
    assert b"Hello there" not in client.get("/pl/blog/x").data
