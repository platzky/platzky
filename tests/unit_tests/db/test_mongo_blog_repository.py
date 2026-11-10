from unittest.mock import Mock, patch

import pytest

from platzky.db.exceptions import NotFoundError
from platzky.db.mongo_blog_repository import MongoBlogRepository
from platzky.models import Post


class TestMongoBlogRepository:
    @pytest.fixture
    def mock_db(self) -> Mock:
        return Mock()

    @pytest.fixture
    def blog(self, mock_db: Mock) -> MongoBlogRepository:
        return MongoBlogRepository(mock_db.posts, mock_db.pages)

    def test_get_all_posts(self, blog: MongoBlogRepository, mock_db: Mock):
        # Mock posts data
        mock_posts = [
            {
                "_id": "1",
                "title": "Post 1",
                "slug": "post-1",
                "content": "Content 1",
                "language": "en",
                "tags": ["tag1"],
                "comments": [],
                "author": "Test Author",
                "contentInMarkdown": "# Post 1",
                "excerpt": "Post excerpt",
                "coverImage": {"url": "/images/post1.jpg"},
                "date": "2023-01-01T00:00:00",
            }
        ]

        mock_find = mock_db.posts.find
        mock_find.return_value = mock_posts

        posts = blog.posts.get_all("en")

        assert len(posts) == 1
        assert isinstance(posts[0], Post)
        assert posts[0].title == "Post 1"
        mock_find.assert_called_once_with({"language": "en"})

    def test_get_post(self, blog: MongoBlogRepository, mock_db: Mock):
        # Mock post data
        mock_post = {
            "_id": "1",
            "title": "Post 1",
            "slug": "post-1",
            "content": "Content 1",
            "language": "en",
            "tags": ["tag1"],
            "comments": [],
            "author": "Test Author",
            "contentInMarkdown": "# Post 1",
            "excerpt": "Post excerpt",
            "coverImage": {"url": "/images/post1.jpg"},
            "date": "2023-01-01T00:00:00",
        }

        mock_find_one = mock_db.posts.find_one
        mock_find_one.return_value = mock_post

        post = blog.posts.get("post-1")

        assert isinstance(post, Post)
        assert post.title == "Post 1"
        mock_find_one.assert_called_once_with({"slug": "post-1"})

    def test_get_post_not_found(self, blog: MongoBlogRepository, mock_db: Mock):
        mock_db.posts.find_one.return_value = None

        with pytest.raises(NotFoundError, match="Post with slug non-existent not found"):
            blog.posts.get("non-existent")

    def test_get_all_pages(self, blog: MongoBlogRepository, mock_db: Mock):
        mock_find = mock_db.pages.find
        mock_find.return_value = [
            {
                "title": "About Tolkien",
                "slug": "about-tolkien",
                "author": "Test Author",
                "contentInMarkdown": "# About",
                "excerpt": "excerpt",
                "language": "en",
                "coverImage": {"url": "/images/tolkien.jpg"},
            }
        ]

        pages = blog.pages.get_all("en")

        assert [page.slug for page in pages] == ["about-tolkien"]
        mock_find.assert_called_once_with({"language": "en"})

    def test_get_page(self, blog: MongoBlogRepository, mock_db: Mock):
        # Mock page data
        mock_page = {
            "_id": "1",
            "title": "Page 1",
            "slug": "page-1",
            "content": "Page content",
            "language": "en",
            "tags": [],
            "comments": [],
            "author": "Page Author",
            "contentInMarkdown": "# Page 1",
            "excerpt": "Page excerpt",
            "coverImage": {"url": "/images/page1.jpg"},
            "date": "2023-01-01T00:00:00",
        }

        mock_find_one = mock_db.pages.find_one
        mock_find_one.return_value = mock_page

        page = blog.pages.get("page-1")

        assert isinstance(page, Post)  # Page is actually Post type in platzky
        assert page.title == "Page 1"
        mock_find_one.assert_called_once_with({"slug": "page-1"})

    def test_get_page_not_found(self, blog: MongoBlogRepository, mock_db: Mock):
        mock_db.pages.find_one.return_value = None

        with pytest.raises(NotFoundError, match="Page with slug non-existent not found"):
            blog.pages.get("non-existent")

    def test_get_posts_by_tag(self, blog: MongoBlogRepository, mock_db: Mock):
        mock_posts = [
            {
                "title": "Tagged Post",
                "slug": "tagged-post",
                "content": "Content",
                "language": "en",
                "tags": ["tag1"],
                "comments": [],
                "author": "Test Author",
                "contentInMarkdown": "# Tagged Post",
                "excerpt": "Excerpt",
                "coverImage": {"url": "/images/post.jpg"},
                "date": "2023-01-01T00:00:00",
            }
        ]
        mock_find = mock_db.posts.find
        mock_find.return_value = mock_posts

        result = blog.posts.get_by_tag("tag1", "en")

        assert len(result) == 1
        assert isinstance(result[0], Post)
        assert result[0].title == "Tagged Post"
        mock_find.assert_called_once_with({"tags": "tag1", "language": "en"})

    def test_add_comment(self, blog: MongoBlogRepository, mock_db: Mock):
        with patch("platzky.db.mongo_blog_repository.datetime.datetime") as mock_datetime:
            test_date = Mock()
            test_date.isoformat.return_value = "2023-01-01T12:00:00"
            mock_datetime.now.return_value = test_date

            blog.posts.add_comment("Test User", "Great post!", "post-1")

            expected_comment = {
                "author": "Test User",
                "comment": "Great post!",
                "date": "2023-01-01T12:00:00",
            }

            mock_db.posts.update_one.assert_called_once_with(
                {"slug": "post-1"}, {"$push": {"comments": expected_comment}}
            )
