import datetime
from unittest.mock import Mock

import pytest

from platzky.db.blog_repository import BlogRepository
from platzky.db.exceptions import NotFoundError
from platzky.db.graphql_blog_repository import GraphQLBlogRepository
from platzky.models import Comment, Post


@pytest.fixture
def mock_client() -> Mock:
    return Mock()


@pytest.fixture
def repository(mock_client: Mock) -> GraphQLBlogRepository:
    return GraphQLBlogRepository(lambda: mock_client)


_MINIMAL_POST = {
    "date": "2023-01-01",
    "language": "en",
    "title": "Test Post",
    "slug": "test-post",
    "author": {"name": "John Doe"},
    "contentInRichText": {"html": "<p>Test content</p>"},
    "excerpt": "Test excerpt",
    "tags": [],
    "coverImage": None,
    "comments": [],
}


class TestPosts:
    def test_get_returns_matching_post(self, repository: GraphQLBlogRepository, mock_client: Mock):
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
                    {
                        "author": "Jane Doe",
                        "comment": "Great post!",
                        "createdAt": "2023-01-02T03:04:05+00:00",
                    }
                ],
                "css": ".masthead { background: teal; }",
            }
        }

        post = repository.posts.get("test-post")

        assert isinstance(post, Post)
        assert post.title == "Test Post"
        assert post.slug == "test-post"
        assert post.css == ".masthead { background: teal; }"
        assert post.coverImage.url == "https://example.com/image.jpg"
        assert post.coverImage.alternateText == "Alt text"
        assert post.comments == [
            Comment(
                author="Jane Doe",
                comment="Great post!",
                date=datetime.datetime(2023, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc),
            )
        ]
        mock_client.execute.assert_called_once()

    def test_get_defaults_css_to_empty_string(
        self, repository: GraphQLBlogRepository, mock_client: Mock
    ):
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

        post = repository.posts.get("test-post")

        assert post.css == ""

    def test_get_raises_not_found_for_unknown_slug(
        self, repository: GraphQLBlogRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {"post": None}

        with pytest.raises(NotFoundError, match="missing"):
            repository.posts.get("missing")

    def test_get_all_returns_posts(self, repository: GraphQLBlogRepository, mock_client: Mock):
        mock_client.execute.return_value = {
            "posts": [
                {
                    "createdAt": "2023-01-01",
                    "author": {"name": "John Doe"},
                    "contentInRichText": {"html": "<p>Test content</p>"},
                    "comments": [
                        {
                            "author": "Jane Doe",
                            "comment": "Great post!",
                            "createdAt": "2023-01-02T03:04:05+00:00",
                        }
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

        posts = repository.posts.get_all("en")

        assert len(posts) == 1
        assert isinstance(posts[0], Post)
        assert posts[0].title == "Test Post"
        assert posts[0].slug == "test-post"
        assert posts[0].coverImage.alternateText == "Alt text"
        assert posts[0].comments == [
            Comment(
                author="Jane Doe",
                comment="Great post!",
                date=datetime.datetime(2023, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc),
            )
        ]
        mock_client.execute.assert_called_once()

    def test_get_by_tag_returns_matching_posts(
        self, repository: GraphQLBlogRepository, mock_client: Mock
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

        posts = repository.posts.get_by_tag("test", "en")

        assert len(posts) == 1
        assert isinstance(posts[0], Post)
        assert posts[0].title == "Test Post"
        assert posts[0].slug == "test-post"
        assert posts[0].coverImage.alternateText == "Alt text"
        mock_client.execute.assert_called_once()

    def test_get_by_tag_uses_requested_language(
        self, repository: GraphQLBlogRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {
            "posts": [
                {
                    "tags": ["test"],
                    "title": "Wpis",
                    "slug": "wpis",
                    "excerpt": "e",
                    "date": "2023-01-01",
                }
            ]
        }

        posts = repository.posts.get_by_tag("test", "pl")

        assert posts[0].language == "pl"

    def test_get_queries_comment_dates_under_the_key_the_parser_reads(
        self, repository: GraphQLBlogRepository, mock_client: Mock
    ):
        """The mock answers whatever the query asks, so only the query text ties it to parsing.

        Comments are parsed from ``createdAt``; an alias such as ``date: createdAt`` would
        make the CMS return them under ``date`` and every post with comments would fail.
        """
        mock_client.execute.return_value = {"post": _MINIMAL_POST}

        repository.posts.get("test-post")

        query = str(mock_client.execute.call_args.args[0])
        assert "date: createdAt" not in query
        assert "createdAt" in query

    def test_get_all_queries_comment_dates_under_the_key_the_parser_reads(
        self, repository: GraphQLBlogRepository, mock_client: Mock
    ):
        """Same guard as for ``get``: the list query must not alias ``createdAt``."""
        mock_client.execute.return_value = {"posts": [_MINIMAL_POST]}

        repository.posts.get_all("en")

        query = str(mock_client.execute.call_args.args[0])
        assert "date: createdAt" not in query
        assert "createdAt" in query

    def test_add_comment_sends_expected_variables(
        self, repository: GraphQLBlogRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {"createComment": {"id": "123"}}

        repository.posts.add_comment("John Doe", "Great post!", "test-post")

        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[1]["variable_values"]
        assert call_args["author"] == "John Doe"
        assert call_args["comment"] == "Great post!"
        assert call_args["slug"] == "test-post"


class TestPages:
    def test_get_returns_matching_page(self, repository: GraphQLBlogRepository, mock_client: Mock):
        mock_client.execute.return_value = {
            "page": {
                "slug": "about",
                "title": "About",
                "contentInMarkdown": "About page content",
                "coverImage": {"url": "https://example.com/image.jpg"},
                "css": ".masthead { background: teal; }",
            }
        }

        page = repository.pages.get("about")

        assert isinstance(page, Post)  # Page is an alias for Post
        assert page.title == "About"
        assert page.contentInMarkdown == "About page content"
        assert page.css == ".masthead { background: teal; }"
        mock_client.execute.assert_called_once()

    def test_get_defaults_css_to_empty_string(
        self, repository: GraphQLBlogRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {
            "page": {
                "slug": "about",
                "title": "About",
                "contentInMarkdown": "About page content",
                "coverImage": {"url": "https://example.com/image.jpg"},
            }
        }

        page = repository.pages.get("about")

        assert page.css == ""

    def test_get_all_is_not_supported_and_queries_nothing(
        self, repository: GraphQLBlogRepository, mock_client: Mock
    ):
        assert repository.pages.get_all("en") == []
        mock_client.execute.assert_not_called()

    def test_get_raises_not_found_for_unknown_slug(
        self, repository: GraphQLBlogRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {"page": None}

        with pytest.raises(NotFoundError, match="missing"):
            repository.pages.get("missing")


def test_graphql_blog_repository_satisfies_blog_repository_protocol(
    repository: GraphQLBlogRepository,
) -> None:
    """Structural check: pyright rejects this assignment if the shape drifts."""
    conforms: BlogRepository = repository
    assert conforms is repository
