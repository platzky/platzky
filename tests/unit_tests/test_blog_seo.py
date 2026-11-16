"""What the blog tells crawlers and feed readers, read from the sitemap, page heads and feed."""

from collections.abc import Mapping, Sequence
from typing import Any
from xml.etree import ElementTree

from bs4 import BeautifulSoup, Tag
from flask.testing import FlaskClient

from platzky.config import Config
from platzky.platzky import create_app_from_config

_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
_LANGUAGES = {
    "en": {"name": "English", "flag": "gb", "country": "GB"},
    "pl": {"name": "Polski", "flag": "pl", "country": "PL"},
}


def _post(slug: str, language: str, extra: Mapping[str, object] | None = None) -> dict[str, Any]:
    return {
        "title": f"title {slug}",
        "slug": slug,
        "author": "author",
        "excerpt": f"excerpt {slug}",
        "contentInMarkdown": "text",
        "language": language,
        **(extra or {}),
    }


def _page(slug: str, language: str) -> dict[str, Any]:
    return _post(slug, language)


def _client(
    posts: Sequence[Mapping[str, Any]],
    pages: Sequence[Mapping[str, Any]] | None = None,
    site_config: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
) -> FlaskClient:
    """Build a client over a site in English and Polish with the given content."""
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
                "DATA": {
                    "site_config": site_config or {},
                    "blog": {"posts": posts, "pages": pages or [], "meta": meta or {}},
                },
            },
        }
    )
    return create_app_from_config(config).test_client()


def _sitemap_locs(client: FlaskClient) -> set[str]:
    root = ElementTree.fromstring(client.get("/sitemap.xml").data)
    return {loc.text or "" for loc in root.iterfind(".//sm:loc", _SITEMAP_NS)}


def _pages_as_homes(posts: Sequence[Mapping[str, Any]]) -> FlaskClient:
    """Build a client whose homes are pages, so the blog index is a page of its own."""
    return _client(
        posts,
        pages=[_page("about", "en"), _page("o-nas", "pl")],
        site_config={
            "localized_content": {
                "en": {"home_page_path": "/blog/page/about"},
                "pl": {"home_page_path": "/blog/page/o-nas"},
            }
        },
    )


def test_sitemap_lists_the_blog_index_of_a_language_with_posts():
    locs = _sitemap_locs(_pages_as_homes([_post("x", "pl")]))

    assert "http://localhost/pl/blog/" in locs


def test_sitemap_leaves_out_the_blog_index_of_a_language_without_posts():
    client = _pages_as_homes([_post("x", "pl")])

    assert client.get("/blog/").status_code == 404
    assert "http://localhost/blog/" not in _sitemap_locs(client)


def _head_url(client: FlaskClient, path: str, selector: str, attribute: str) -> str:
    """Read the URL that the page's head tag matching `selector` declares in `attribute`."""
    tag = BeautifulSoup(client.get(path).data, "html.parser").select_one(selector)
    assert isinstance(tag, Tag)
    return str(tag.get(attribute))


def test_a_page_shown_as_the_home_declares_the_home_as_its_og_url_and_canonical():
    client = _pages_as_homes([_post("x", "pl")])

    og_url = _head_url(client, "/pl/blog/page/o-nas", 'meta[property="og:url"]', "content")
    canonical = _head_url(client, "/pl/blog/page/o-nas", 'link[rel="canonical"]', "href")

    assert og_url == canonical == "http://localhost/pl/"


def test_a_page_of_its_own_declares_its_own_address_as_og_url_and_canonical():
    client = _pages_as_homes([_post("x", "pl")])

    og_url = _head_url(client, "/pl/blog/x", 'meta[property="og:url"]', "content")
    canonical = _head_url(client, "/pl/blog/x", 'link[rel="canonical"]', "href")

    assert og_url == canonical == "http://localhost/pl/blog/x"


def _meta_descriptions(client: FlaskClient, path: str) -> dict[str, str]:
    """Read the descriptions that the page's head declares, by the tag that declares each."""
    soup = BeautifulSoup(client.get(path).data, "html.parser")
    selectors = {
        "description": 'meta[name="description"]',
        "og": 'meta[property="og:description"]',
        "twitter": 'meta[name="twitter:description"]',
    }
    return {
        name: (
            str(tag.get("content")).strip()
            if isinstance(tag := soup.select_one(selector), Tag)
            else ""
        )
        for name, selector in selectors.items()
    }


def test_a_page_describes_itself_by_its_excerpt_and_the_home_by_the_site_description():
    client = _client(
        [_post("x", "pl")],
        pages=[_page("o-nas", "pl")],
        site_config={"localized_content": {"pl": {"app_description": "opis serwisu"}}},
    )

    page = _meta_descriptions(client, "/pl/blog/page/o-nas")
    home = _meta_descriptions(client, "/pl/")

    assert page == {
        "description": "excerpt o-nas",
        "og": "excerpt o-nas",
        "twitter": "excerpt o-nas",
    }
    assert home["description"] == "opis serwisu"


def test_a_page_without_an_excerpt_describes_itself_by_the_site_description():
    client = _client(
        [_post("x", "pl")],
        pages=[_post("o-nas", "pl", {"excerpt": ""})],
        site_config={"localized_content": {"pl": {"app_description": "opis serwisu"}}},
    )

    assert _meta_descriptions(client, "/pl/blog/page/o-nas") == {
        "description": "opis serwisu",
        "og": "opis serwisu",
        "twitter": "opis serwisu",
    }


def test_a_post_without_an_excerpt_describes_itself_by_the_site_description():
    client = _client(
        [_post("with", "pl"), _post("without", "pl", {"excerpt": ""})],
        site_config={"localized_content": {"pl": {"app_description": "opis serwisu"}}},
    )

    assert _meta_descriptions(client, "/pl/blog/without") == {
        "description": "opis serwisu",
        "og": "opis serwisu",
        "twitter": "opis serwisu",
    }
    assert _meta_descriptions(client, "/pl/blog/with")["description"] == "excerpt with"


def _hreflangs(client: FlaskClient, path: str) -> dict[str, str]:
    """Read the alternates that the page's head declares, by language."""
    soup = BeautifulSoup(client.get(path).data, "html.parser")
    return {str(tag["hreflang"]): str(tag["href"]) for tag in soup.select("link[hreflang]")}


def test_blog_index_declares_alternates_only_in_languages_with_posts():
    client = _pages_as_homes([_post("x", "pl")])

    assert client.get("/blog/").status_code == 404
    assert client.get("/pl/blog/").status_code == 200
    assert _hreflangs(client, "/pl/blog/") == {"pl": "http://localhost/pl/blog/"}


def test_blog_index_declares_an_alternate_in_every_language_with_posts():
    client = _pages_as_homes([_post("x", "pl"), _post("y", "en")])

    assert _hreflangs(client, "/pl/blog/") == {
        "en": "http://localhost/blog/",
        "pl": "http://localhost/pl/blog/",
        "x-default": "http://localhost/blog/",
    }


def _feed(client: FlaskClient, path: str = "/pl/blog/feed") -> ElementTree.Element:
    return ElementTree.fromstring(client.get(path).data)


def _items(feed: ElementTree.Element) -> dict[str, ElementTree.Element]:
    """Index the feed's items by title."""
    return {item.findtext("title") or "": item for item in feed.iterfind("channel/item")}


def test_feed_describes_the_channel_as_the_blog_index_page_does():
    client = _client(
        [_post("x", "pl")],
        site_config={"localized_content": {"pl": {"app_description": "Opis serwisu"}}},
        meta={"pl": {"description": "Opis bloga"}},
    )

    assert _feed(client).findtext("channel/description") == "Opis bloga"


def test_feed_describes_the_channel_as_the_site_when_the_blog_has_no_description():
    client = _client(
        [_post("x", "pl")],
        site_config={"localized_content": {"pl": {"app_description": "Opis serwisu"}}},
    )

    assert _feed(client).findtext("channel/description") == "Opis serwisu"


def test_feed_links_to_the_blog_and_its_posts_in_the_feeds_language():
    feed = _feed(_client([_post("x", "pl")]))

    assert feed.findtext("channel/link") == "http://localhost/pl/blog/"
    item = _items(feed)["title x"]
    assert item.findtext("link") == "http://localhost/pl/blog/x"
    assert item.findtext("guid") == "http://localhost/pl/blog/x"


def test_feed_dates_a_post_that_has_a_date_in_rfc_822():
    feed = _feed(_client([_post("x", "pl", {"date": "2021-02-19T10:30:00+00:00"})]))

    assert _items(feed)["title x"].findtext("pubDate") == "Fri, 19 Feb 2021 10:30:00 +0000"


def test_feed_leaves_out_the_date_of_a_post_without_one():
    feed = _feed(_client([_post("x", "pl")]))

    assert _items(feed)["title x"].find("pubDate") is None


def test_feed_attaches_the_cover_image_of_a_post_that_has_one():
    cover = {"url": "https://example.com/cover.jpg", "alternateText": "cover"}
    feed = _feed(_client([_post("x", "pl", {"coverImage": cover})]))

    enclosure = _items(feed)["title x"].find("enclosure")
    assert enclosure is not None
    assert enclosure.get("url") == "https://example.com/cover.jpg"


def test_feed_attaches_nothing_to_a_post_without_a_cover_image():
    feed = _feed(_client([_post("x", "pl")]))

    assert _items(feed)["title x"].find("enclosure") is None
