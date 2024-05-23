# TODO: create smaller and more meaningful tests
# These tests do not test database queries - it mocks queries. Tests which test queries should
# be integration tests.
# Most of those tests just check if some content is displayed and if response code is as it should
# These should also check how data is formatted, checked for multiple elements, etc.

from unittest.mock import MagicMock

import pytest

from platzky.blog import blog
from platzky.config import Config
from platzky.platzky import create_engine
from platzky.models import Post, Image

from freezegun import freeze_time

from platzky.models import Comment

mocked_post_json = {
    "title": "post title",
    "language": "en",
    "slug": "slug",
    "author": "author",
    "tags": ["tag/1", "tagtag"],
    "contentInMarkdown": "This is some content",
    "date": "2021-02-19",
    "coverImage": {
        "alternateText": "text which is alternative",
        "url": "https://media.graphcms.com/XvmCDUjYTIq4c9wOIseo",
    },
    "comments": [
        {
            "time_delta": "10 months ago",
            "date": "2021-02-19T00:00:00",
            "comment": "This is some comment",
            "author": "author",
        }
    ],
}
mocked_post = Post.model_validate(mocked_post_json)


@pytest.fixture
def test_app():
    db_mock = MagicMock()
    db_mock.get_post.return_value = mocked_post
    db_mock.get_posts_by_tag.return_value = [mocked_post]
    db_mock.get_all_posts.return_value = [mocked_post]
    config = Config.model_validate(
        {
            "BLOG_PREFIX": "/prefix",  # TODO test without prefix in config (same for seo tests)
            "SECRET_KEY": "secret",
            "PLUGINS": [],
            "USE_WWW": False,
            "SEO_PREFIX": "/",
            "APP_NAME": "app name",
            "LANGUAGES": {
                "en": {"name": "English", "flag": "uk", "domain": "localhost"}
            },
            "DOMAIN_TO_LANG": {"localhost": "en"},
            "DB": {"TYPE": "json_file", "PATH": ""},
            "DEBUG": True,
            "TESTING": True,
        }
    )
    app = create_engine(config, db_mock)
    blog_blueprint = blog.create_blog_blueprint(
        db_mock, config.blog_prefix, app.get_locale
    )

    app.register_blueprint(blog_blueprint)
    return app.test_client()


def old_comment_on_page(response):
    return b"This is some comment" in response.data


def post_contents_on_page(response):
    return b"This is some content" in response.data


def test_usual_post(test_app):
    response = test_app.get("/prefix/slug")
    assert response.status_code == 200
    assert old_comment_on_page(response)
    assert post_contents_on_page(response)


def test_not_existing_post(test_app):
    test_app.application.db.get_post.return_value = None
    response = test_app.get("/prefix/slughorn")
    assert response.status_code == 404


def test_rss_feed(test_app):
    response = test_app.get("/prefix/feed")
    assert response.status_code == 200
    assert b"post title" in response.data
    assert not old_comment_on_page(response)
    assert not post_contents_on_page(response)


def test_all_posts(test_app):
    response = test_app.get("/prefix/")
    assert response.status_code == 200
    assert b"post title" in response.data
    assert not old_comment_on_page(response)
    assert not post_contents_on_page(response)


def test_tag_filter(test_app):
    response = test_app.get("/prefix/tag/tag1")
    assert response.status_code == 200
    assert b"post title" in response.data
    assert not old_comment_on_page(response)
    assert not post_contents_on_page(response)


def test_posting_new_comment(test_app):
    fresh_comment_content = "Fresh comment"
    response = test_app.post(
        "/prefix/slug",
        data={"author_name": "comments author", "comment": fresh_comment_content},
    )
    assert response.status_code == 200
    assert old_comment_on_page(response)
    assert f"{fresh_comment_content}".encode("utf-8") in response.data


def test_not_existing_page(test_app):
    test_app.application.db.get_page.return_value = None
    response = test_app.get("/prefix/page/not-existing-page")
    assert response.status_code == 404


def test_page(test_app):
    test_app.application.db.get_page.return_value = mocked_post
    response = test_app.get("/prefix/page/blabla")
    assert response.status_code == 200


def test_page_without_cover_image(test_app):
    mocked_post.coverImage = Image()
    test_app.application.db.get_page.return_value = mocked_post
    response = test_app.get("/prefix/page/blabla")
    assert response.status_code == 200


# TODO create those tests
# def test_post_without_cover_image(test_app):


@freeze_time("2022-01-01")
def test_comment_formatting():
    comment_raw = {
        "date": "2021-02-19T00:00:00",
        "comment": "komentarz",
        "author": "autor",
    }
    comment = Comment.model_validate(comment_raw)
    assert comment.time_delta == "10 months ago"
