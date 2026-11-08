import datetime
from collections.abc import Callable
from unittest.mock import Mock

import pytest

from platzky.db.blog_repository import BlogRepository, PostRepository
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

# Every post query; `get` is wrapped in a list so all three return list[Post].
_POST_QUERIES: list[Callable[[PostRepository], list[Post]]] = [
    lambda posts: [posts.get("test-post")],
    lambda posts: posts.get_all("en"),
    lambda posts: posts.get_by_tag("t", "en"),
]


@pytest.fixture(params=_POST_QUERIES, ids=["get", "get_all", "get_by_tag"])
def query_posts(request: pytest.FixtureRequest) -> Callable[[PostRepository], list[Post]]:
    return request.param


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

    def test_get_by_tag_returns_full_posts(
        self, repository: GraphQLBlogRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {
            "posts": [
                {
                    **_MINIMAL_POST,
                    "language": "pl",
                    "tags": ["test"],
                    "css": ".a { color: red; }",
                    "comments": [
                        {
                            "author": "Jane Doe",
                            "comment": "Great post!",
                            "createdAt": "2023-01-02T03:04:05+00:00",
                        }
                    ],
                }
            ]
        }

        posts = repository.posts.get_by_tag("test", "pl")

        assert len(posts) == 1
        assert posts[0].author == "John Doe"
        assert posts[0].language == "pl"
        assert posts[0].contentInMarkdown == "<p>Test content</p>"
        assert posts[0].css == ".a { color: red; }"
        assert len(posts[0].comments) == 1

    def test_get_by_tag_sends_tag_and_language(
        self, repository: GraphQLBlogRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {"posts": []}

        repository.posts.get_by_tag("test", "pl")

        assert mock_client.execute.call_args.kwargs["variable_values"] == {
            "tag": "test",
            "lang": "pl",
        }

    def test_null_optional_fields_become_empty_strings(
        self,
        repository: GraphQLBlogRepository,
        mock_client: Mock,
        query_posts: Callable[[PostRepository], list[Post]],
    ):
        raw = {**_MINIMAL_POST, "contentInRichText": None, "excerpt": None, "author": None}
        mock_client.execute.return_value = {"post": raw, "posts": [raw]}

        post = query_posts(repository.posts)[0]

        assert (post.contentInMarkdown, post.excerpt, post.author) == ("", "", "")

    def test_queries_request_css_and_language(
        self,
        repository: GraphQLBlogRepository,
        mock_client: Mock,
        query_posts: Callable[[PostRepository], list[Post]],
    ):
        mock_client.execute.return_value = {"post": _MINIMAL_POST, "posts": [_MINIMAL_POST]}

        query_posts(repository.posts)

        query = str(mock_client.execute.call_args.args[0])
        assert "css" in query
        assert "language" in query

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
        mock_client.execute.side_effect = [{"post": {"id": "1"}}, {"createComment": {"id": "123"}}]

        repository.posts.add_comment("John Doe", "Great post!", "test-post")

        call_args = mock_client.execute.call_args[1]["variable_values"]
        assert call_args["author"] == "John Doe"
        assert call_args["comment"] == "Great post!"
        assert call_args["slug"] == "test-post"

    def test_add_comment_raises_not_found_for_unknown_slug(
        self, repository: GraphQLBlogRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {"post": None}

        with pytest.raises(NotFoundError, match="missing"):
            repository.posts.add_comment("John Doe", "Great post!", "missing")

        mock_client.execute.assert_called_once()

    def test_add_comment_propagates_mutation_errors(
        self, repository: GraphQLBlogRepository, mock_client: Mock
    ):
        mock_client.execute.side_effect = [{"post": {"id": "1"}}, RuntimeError("boom")]

        with pytest.raises(RuntimeError, match="boom"):
            repository.posts.add_comment("John Doe", "Great post!", "test-post")


class TestPages:
    def test_get_returns_matching_page(self, repository: GraphQLBlogRepository, mock_client: Mock):
        mock_client.execute.return_value = {
            "page": {
                "slug": "about",
                "title": "About",
                "contentInMarkdown": "About page content",
                "coverImage": {"url": "https://example.com/image.jpg"},
                "css": ".masthead { background: teal; }",
                "lang": "pl",
                "author": {"name": "Jane Doe"},
            }
        }

        page = repository.pages.get("about")

        assert isinstance(page, Post)  # Page is an alias for Post
        assert page.title == "About"
        assert page.contentInMarkdown == "About page content"
        assert page.css == ".masthead { background: teal; }"
        assert page.language == "pl"
        assert page.author == "Jane Doe"
        assert page.excerpt == ""
        assert page.date is None
        assert page.tags == []
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
                "lang": "en",
                "author": None,
            }
        }

        page = repository.pages.get("about")

        assert page.css == ""
        assert page.author == ""

    def test_get_all_returns_pages_for_language(
        self, repository: GraphQLBlogRepository, mock_client: Mock
    ):
        mock_client.execute.return_value = {
            "pages": [
                {
                    "slug": "o-nas",
                    "title": "O nas",
                    "contentInMarkdown": "Tresc",
                    "css": None,
                    "lang": "pl",
                    "author": {"name": "Jane Doe"},
                    "coverImage": None,
                }
            ]
        }

        pages = repository.pages.get_all("pl")

        assert [(p.slug, p.language, p.author) for p in pages] == [("o-nas", "pl", "Jane Doe")]
        assert mock_client.execute.call_args.kwargs["variable_values"] == {"lang": "pl"}

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
