import base64
import json
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from github.ContentFile import ContentFile
from github.Repository import Repository

from platzky.db.exceptions import ReadOnlyStorageError
from platzky.db.github_json_db import (
    GithubJsonDb,
    GithubJsonDbConfig,
    db_config_type,
    db_from_config,
)

SITE_DESCRIPTION = {"en": "Hello"}
POST = {
    "author": "Ann",
    "slug": "post-1",
    "title": "First post",
    "contentInMarkdown": "Body",
    "excerpt": "Short",
    "comments": [],
}
SITE_DATA = {"site_content": {"app_description": SITE_DESCRIPTION, "posts": [POST]}}
DOWNLOAD_URL = "https://example.com/file.json"


def make_content_file(data: dict[str, Any], *, inline: bool = True) -> Mock:
    """Fake GitHub file whose `content`, `decoded_content` and the payload agree.

    With inline=False the content is empty, as GitHub returns for large files,
    so the DB has to fetch `download_url` instead.
    """
    raw = json.dumps(data).encode()
    file = Mock(spec=ContentFile)
    file.content = base64.b64encode(raw).decode() if inline else ""
    file.decoded_content = raw
    file.download_url = DOWNLOAD_URL
    return file


@pytest.fixture
def repo() -> Iterator[Mock]:
    """The repository returned by a patched Github client."""
    with patch("platzky.db.github_json_db.Github") as MockGithub:
        mock_repo = Mock(spec=Repository)
        MockGithub.return_value.get_repo.return_value = mock_repo
        yield mock_repo


def test_returns_correct_db_config_type():
    assert db_config_type() == GithubJsonDbConfig


def test_creates_github_json_db_from_config(repo: Mock):
    repo.get_contents.return_value = make_content_file(SITE_DATA)

    config = GithubJsonDbConfig(
        TYPE="github_json_db",
        GITHUB_TOKEN="fake_token",
        REPO_NAME="fake_repo",
        PATH_TO_FILE="path/to/file.json",
        BRANCH_NAME="main",
    )
    db = db_from_config(config)
    assert isinstance(db, GithubJsonDb)
    assert db.branch_name == "main"
    assert db.file_path == "path/to/file.json"
    assert db.get_site_settings().app_description == SITE_DESCRIPTION


def test_retrieves_data_from_github_file(repo: Mock):
    repo.get_contents.return_value = make_content_file(SITE_DATA)

    db = GithubJsonDb("fake_token", "fake_repo", "main", "path/to/file.json")

    assert db.get_site_settings().app_description == SITE_DESCRIPTION
    assert [post.slug for post in db.get_all_posts("en")] == ["post-1"]
    repo.get_contents.assert_called_once_with("path/to/file.json", ref="main")


def test_raises_error_for_directory_path(repo: Mock):
    repo.get_contents.return_value = [MagicMock()]  # Simulate directory

    with pytest.raises(
        ValueError, match=r"Path 'path/to/file\.json' points to a directory, not a file"
    ):
        GithubJsonDb("fake_token", "fake_repo", "main", "path/to/file.json")


def test_retrieves_data_via_download_url_when_content_is_empty(repo: Mock):
    repo.get_contents.return_value = make_content_file(SITE_DATA, inline=False)

    with patch("platzky.db.github_json_db.requests.get") as mock_requests:
        mock_requests.return_value.text = json.dumps(SITE_DATA)
        db = GithubJsonDb("fake_token", "fake_repo", "main", "path/to/file.json")

    mock_requests.assert_called_once_with(DOWNLOAD_URL, timeout=40)
    assert db.get_site_settings().app_description == SITE_DESCRIPTION


def test_raises_error_for_invalid_json_content(repo: Mock):
    file = make_content_file(SITE_DATA)
    file.decoded_content = b"invalid json"
    repo.get_contents.return_value = file

    with pytest.raises(ValueError, match="Error parsing JSON content: Expecting value"):
        GithubJsonDb("fake_token", "fake_repo", "main", "path/to/file.json")


def test_add_comment_raises_read_only_storage_error(repo: Mock):
    """GithubJsonDb is read-only: writes must fail loudly, not vanish silently."""
    repo.get_contents.return_value = make_content_file(SITE_DATA)

    db = GithubJsonDb("fake_token", "fake_repo", "main", "path/to/file.json")

    with pytest.raises(ReadOnlyStorageError):
        db.add_comment("Test User", "New comment", "post-1")
