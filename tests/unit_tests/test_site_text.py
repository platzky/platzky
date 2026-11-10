"""Per-language site texts (localized_content with top-level defaults) in rendered pages."""

from typing import Any
from xml.etree import ElementTree

import pytest
from bs4 import BeautifulSoup, Tag
from flask import render_template_string

from platzky.config import Config
from platzky.engine import Engine
from platzky.platzky import create_app_from_config

_LANGUAGES = {
    "en": {"name": "English", "flag": "us", "country": "US"},
    "pl": {"name": "Polski", "flag": "pl", "country": "PL"},
}
_CONFIG_NAME = "configName"
_NAMES = {"en": "DropLoop", "pl": "DropLoop PL"}
_TITLES = {"en": "DropLoop - play", "pl": "DropLoop - graj"}
_DESCRIPTIONS = {"en": "About us", "pl": "O nas"}
_DEFAULT_NAME = "Default name"
_DEFAULT_TITLE = "Default title"
_DEFAULT_DESCRIPTION = "Default description"
_PLAIN_PAGE = "/plain"


_POSTS = [
    {
        "title": title,
        "slug": slug,
        "language": lang,
        "excerpt": "excerpt",
        "author": "author",
        "tags": [],
        "contentInMarkdown": title,
        "date": "2021-02-19",
        "comments": [],
    }
    for title, slug, lang in [("English post", "english-post", "en"), ("Polski wpis", "wpis", "pl")]
]


def _build_app(site_content: dict[str, Any]) -> Engine:
    config = Config.model_validate(
        {
            "APP_NAME": _CONFIG_NAME,
            "SECRET_KEY": "secret",  # NOSONAR - hardcoded secret acceptable in tests
            "USE_WWW": False,
            "BLOG_PREFIX": "/blog",
            "LANGUAGES": _LANGUAGES,
            "DEFAULT_LANGUAGE": "en",
            "DB": {"TYPE": "json", "DATA": {"site_content": {"posts": _POSTS, **site_content}}},
        }
    )
    app = create_app_from_config(config)

    def plain() -> str:
        return render_template_string('{% extends "base.html" %}')

    app.add_url_rule(_PLAIN_PAGE, "test_plain", plain)
    app.add_url_rule("/pl" + _PLAIN_PAGE, "test_plain_pl", plain)
    return app


def _soup(app: Engine, path: str) -> BeautifulSoup:
    response = app.test_client().get(path)
    assert response.status_code == 200
    return BeautifulSoup(response.data, "html.parser")


def _title(soup: BeautifulSoup) -> str:
    tag = soup.find("title")
    assert isinstance(tag, Tag)
    return tag.get_text(strip=True)


def _navbar_brand(soup: BeautifulSoup) -> str:
    tag = soup.find("a", class_="navbar-brand")
    assert isinstance(tag, Tag)
    return tag.get_text(strip=True)


def _feed_title(feed: bytes) -> str | None:
    return ElementTree.fromstring(feed).findtext("channel/title")


def _og_site_name(soup: BeautifulSoup) -> str:
    tag = soup.find("meta", attrs={"property": "og:site_name"})
    assert isinstance(tag, Tag)
    return str(tag.get("content"))


def _description(soup: BeautifulSoup) -> str:
    tag = soup.find("meta", attrs={"name": "description"})
    assert isinstance(tag, Tag)
    return str(tag.get("content"))


_PER_LANGUAGE: dict[str, Any] = {
    "localized_content": {
        "en": {
            "app_name": "DropLoop",
            "app_title": "DropLoop - play",
            "app_description": "About us",
        },
        "pl": {
            "app_name": "DropLoop PL",
            "app_title": "DropLoop - graj",
            "app_description": "O nas",
        },
    }
}
_BY_PATH = [("", "en"), ("/pl", "pl")]


@pytest.mark.parametrize(("prefix", "lang"), _BY_PATH)
def test_blog_index_title_suffix_uses_localized_app_name(prefix: str, lang: str):
    app = _build_app(_PER_LANGUAGE)

    soup = _soup(app, f"{prefix}/blog/")

    assert _title(soup) == f"Blog – {_NAMES[lang]}"  # noqa: RUF001


@pytest.mark.parametrize(("prefix", "lang"), _BY_PATH)
def test_og_site_name_uses_localized_app_name(prefix: str, lang: str):
    app = _build_app(_PER_LANGUAGE)

    soup = _soup(app, f"{prefix}/blog/")

    assert _og_site_name(soup) == _NAMES[lang]


@pytest.mark.parametrize(("prefix", "lang"), _BY_PATH)
def test_logo_alt_uses_localized_app_name(prefix: str, lang: str):
    app = _build_app({**_PER_LANGUAGE, "logo_url": "/logo.png"})

    soup = _soup(app, f"{prefix}/blog/")

    image = soup.find("img", attrs={"class": "logo"})
    assert isinstance(image, Tag)
    assert image.get("alt") == f"{_NAMES[lang]} logo"


@pytest.mark.parametrize(("prefix", "lang"), _BY_PATH)
def test_navbar_brand_text_without_logo_uses_localized_app_name(prefix: str, lang: str):
    app = _build_app(_PER_LANGUAGE)

    soup = _soup(app, f"{prefix}/blog/")

    assert _navbar_brand(soup) == _NAMES[lang]


@pytest.mark.parametrize(("prefix", "lang"), _BY_PATH)
def test_rss_feed_title_uses_localized_app_name(prefix: str, lang: str):
    app = _build_app(_PER_LANGUAGE)

    response = app.test_client().get(f"{prefix}/blog/feed")

    assert response.status_code == 200
    assert _feed_title(response.data) == _NAMES[lang]


@pytest.mark.parametrize(("prefix", "lang"), _BY_PATH)
def test_page_without_own_title_shows_localized_app_title(prefix: str, lang: str):
    app = _build_app(_PER_LANGUAGE)

    soup = _soup(app, f"{prefix}{_PLAIN_PAGE}")

    assert _title(soup) == _TITLES[lang]


@pytest.mark.parametrize(("prefix", "lang"), _BY_PATH)
def test_meta_description_uses_localized_app_description(prefix: str, lang: str):
    app = _build_app(_PER_LANGUAGE)

    soup = _soup(app, f"{prefix}{_PLAIN_PAGE}")

    assert _description(soup) == _DESCRIPTIONS[lang]


@pytest.mark.parametrize(("prefix", "lang"), _BY_PATH)
def test_localized_logo_url_is_rendered_per_language(prefix: str, lang: str):
    app = _build_app(
        {
            "logo_url": "/default.png",
            "localized_content": {"pl": {"logo_url": "/pl.png"}},
        }
    )

    soup = _soup(app, f"{prefix}/blog/")

    image = soup.find("img", attrs={"class": "logo"})
    assert isinstance(image, Tag)
    assert image.get("src") == {"en": "/default.png", "pl": "/pl.png"}[lang]


def test_top_level_defaults_are_used_for_language_without_localized_entry():
    app = _build_app(
        {
            "app_name": _DEFAULT_NAME,
            "app_title": _DEFAULT_TITLE,
            "app_description": _DEFAULT_DESCRIPTION,
            "localized_content": {"en": {"app_name": _NAMES["en"]}},
        }
    )

    en = _soup(app, "/blog/")
    pl = _soup(app, "/pl/blog/")
    pl_plain = _soup(app, "/pl" + _PLAIN_PAGE)

    assert _og_site_name(en) == _NAMES["en"]
    assert _og_site_name(pl) == _DEFAULT_NAME
    assert _title(pl) == f"Blog – {_DEFAULT_NAME}"  # noqa: RUF001
    assert _title(pl_plain) == _DEFAULT_TITLE
    assert _description(pl_plain) == _DEFAULT_DESCRIPTION


def test_app_title_missing_falls_back_to_localized_app_name():
    app = _build_app({"localized_content": {"pl": {"app_name": _NAMES["pl"]}}})

    soup = _soup(app, "/pl" + _PLAIN_PAGE)

    assert _title(soup) == _NAMES["pl"]


def test_app_description_missing_falls_back_to_localized_app_name():
    app = _build_app({"localized_content": {"pl": {"app_name": _NAMES["pl"]}}})

    soup = _soup(app, "/pl" + _PLAIN_PAGE)

    assert _description(soup) == _NAMES["pl"]


def test_app_name_missing_for_a_language_falls_back_to_config_app_name():
    app = _build_app({"localized_content": {"en": {"app_name": _NAMES["en"]}}})

    pl_soup = _soup(app, "/pl/blog/")
    en_soup = _soup(app, "/blog/")

    assert _title(pl_soup) == f"Blog – {_CONFIG_NAME}"  # noqa: RUF001
    assert _og_site_name(pl_soup) == _CONFIG_NAME
    assert _title(en_soup) == f"Blog – {_NAMES['en']}"  # noqa: RUF001


@pytest.mark.parametrize("prefix", ["", "/pl"])
def test_without_any_site_text_keys_everything_uses_config_app_name(prefix: str):
    app = _build_app({"logo_url": "/logo.png"})

    blog = _soup(app, f"{prefix}/blog/")
    plain = _soup(app, f"{prefix}{_PLAIN_PAGE}")
    feed = app.test_client().get(f"{prefix}/blog/feed")

    assert _title(blog) == f"Blog – {_CONFIG_NAME}"  # noqa: RUF001
    assert _title(plain) == _CONFIG_NAME
    assert _description(plain) == _CONFIG_NAME
    assert _og_site_name(blog) == _CONFIG_NAME
    image = blog.find("img", attrs={"class": "logo"})
    assert isinstance(image, Tag)
    assert image.get("alt") == f"{_CONFIG_NAME} logo"
    assert _feed_title(feed.data) == _CONFIG_NAME
