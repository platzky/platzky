from collections.abc import Iterator
from unittest.mock import Mock, patch

import pytest

from platzky.db.blog_storage import BlogStorage
from platzky.db.exceptions import NotFoundError
from platzky.db.graphql_blog_storage import GraphQLBlogStorage
from platzky.models import Post


@pytest.fixture
def mock_client() -> Mock:
    return Mock()


@pytest.fixture
def storage(mock_client: Mock) -> Iterator[GraphQLBlogStorage]:
    # Client stays patched for the whole test (not just fixture setup): the
    # lazy client is built on the test's first real call, so the patch must
    # still be active at that point, not just during construction.
    with patch("platzky.db.graphql_client.Client", return_value=mock_client):
        yield GraphQLBlogStorage(
            "https://test.endpoint", "test_token"
        )  # NOSONAR - hardcoded token acceptable in tests


class TestPosts:
    def test_get_returns_matching_post(self, storage: GraphQLBlogStorage, mock_client: Mock):
        mock_client.execute.return_value = {
            "post": {
                "date": "2023-01-01",
                "language": "en",
                "title": "Test Post",
                "slug": "test-post",
                "author": {"name": "John Doe"},
                "contentInRichText": {"markdown": "Test content", "html": "<p>Test content</p>"},
                "excerpt": "Test excerpt",
                "tags": ["test", "example"],
                "coverImage": {
                    "alternateText": "Alt text",
                    "image": {"url": "https://example.com/image.jpg"},
                },
                "comments": [
                    {"author": "Jane Doe", "comment": "Great post!", "createdAt": "2023-01-01"}
                ],
                "css": ".masthead { background: teal; }",
            }
        }

        post = storage.posts.get("test-post")

        assert isinstance(post, Post)
        assert post.title == "Test Post"
        assert post.slug == "test-post"
        assert post.css == ".masthead { background: teal; }"
        mock_client.execute.assert_called_once()

    def test_get_defaults_css_to_empty_string(self, storage: GraphQLBlogStorage, mock_client: Mock):
        mock_client.execute.return_value = {
            "post": {
                "date": "2023-01-01",
                "language": "en",
                "title": "Test Post",
                "slug": "test-post",
                "author": {"name": "John Doe"},
                "contentInRichText": {"markdown": "Test content", "html": "<p>Test content</p>"},
                "excerpt": "Test excerpt",
                "tags": ["test", "example"],
                "coverImage": {
                    "alternateText": "Alt text",
                    "image": {"url": "https://example.com/image.jpg"},
                },
                "comments": [],
                "css": None,
            }
        }

        post = storage.posts.get("test-post")

        assert post.css == ""

    def test_get_raises_not_found_for_unknown_slug(
        self, storage: GraphQLBlogStorage, mock_client: Mock
    ):
        mock_client.execute.return_value = {"post": None}

        with pytest.raises(NotFoundError, match="missing"):
            storage.posts.get("missing")

    def test_get_all_returns_posts(self, storage: GraphQLBlogStorage, mock_client: Mock):
        mock_client.execute.return_value = {
            "posts": [
                {
                    "createdAt": "2023-01-01",
                    "author": {"name": "John Doe"},
                    "contentInRichText": {"html": "<p>Test content</p>"},
                    "comments": [
                        {"author": "Jane Doe", "comment": "Great post!", "createdAt": "2023-01-01"}
                    ],
                    "date": "2023-01-01",
                    "title": "Test Post",
                    "excerpt": "Test excerpt",
                    "slug": "test-post",
                    "tags": ["test", "example"],
                    "language": "en",
                    "coverImage": {
                        "alternateText": "Alt text",
                        "image": {"url": "https://example.com/image.jpg"},
                    },
                }
            ]
        }

        posts = storage.posts.get_all("en")

        assert len(posts) == 1
        assert isinstance(posts[0], Post)
        assert posts[0].title == "Test Post"
        assert posts[0].slug == "test-post"
        mock_client.execute.assert_called_once()

    def test_get_by_tag_returns_matching_posts(
        self, storage: GraphQLBlogStorage, mock_client: Mock
    ):
        mock_client.execute.return_value = {
            "posts": [
                {
                    "tags": ["test", "example"],
                    "title": "Test Post",
                    "slug": "test-post",
                    "excerpt": "Test excerpt",
                    "date": "2023-01-01",
                    "coverImage": {
                        "alternateText": "Alt text",
                        "image": {"url": "https://example.com/image.jpg"},
                    },
                }
            ]
        }

        posts = storage.posts.get_by_tag("test", "en")

        assert len(posts) == 1
        assert isinstance(posts[0], Post)
        assert posts[0].title == "Test Post"
        assert posts[0].slug == "test-post"
        mock_client.execute.assert_called_once()

    def test_add_comment_sends_expected_variables(
        self, storage: GraphQLBlogStorage, mock_client: Mock
    ):
        mock_client.execute.return_value = {"createComment": {"id": "123"}}

        storage.posts.add_comment("John Doe", "Great post!", "test-post")

        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[1]["variable_values"]
        assert call_args["author"] == "John Doe"
        assert call_args["comment"] == "Great post!"
        assert call_args["slug"] == "test-post"


class TestPages:
    def test_get_returns_matching_page(self, storage: GraphQLBlogStorage, mock_client: Mock):
        mock_client.execute.return_value = {
            "page": {
                "slug": "about",
                "title": "About",
                "contentInMarkdown": "About page content",
                "coverImage": {"url": "https://example.com/image.jpg"},
                "css": ".masthead { background: teal; }",
            }
        }

        page = storage.pages.get("about")

        assert isinstance(page, Post)  # Page is an alias for Post
        assert page.title == "About"
        assert page.contentInMarkdown == "About page content"
        assert page.css == ".masthead { background: teal; }"
        mock_client.execute.assert_called_once()

    def test_get_defaults_css_to_empty_string(self, storage: GraphQLBlogStorage, mock_client: Mock):
        mock_client.execute.return_value = {
            "page": {
                "slug": "about",
                "title": "About",
                "contentInMarkdown": "About page content",
                "coverImage": {"url": "https://example.com/image.jpg"},
            }
        }

        page = storage.pages.get("about")

        assert page.css == ""

    def test_get_raises_not_found_for_unknown_slug(
        self, storage: GraphQLBlogStorage, mock_client: Mock
    ):
        mock_client.execute.return_value = {"page": None}

        with pytest.raises(NotFoundError, match="missing"):
            storage.pages.get("missing")


def test_graphql_blog_storage_satisfies_blog_storage_protocol(
    storage: GraphQLBlogStorage,
) -> None:
    """Structural check: pyright rejects this assignment if the shape drifts."""
    conforms: BlogStorage = storage
    assert conforms is storage
