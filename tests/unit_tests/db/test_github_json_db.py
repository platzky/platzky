from unittest.mock import MagicMock, patch

import pytest

from platzky.db.github_json_db import (
    GithubJsonDb,
    GithubJsonDbConfig,
    db_config_type,
    db_from_config,
    get_db,
)


def test_returns_correct_db_config_type():
    assert db_config_type() == GithubJsonDbConfig


def test_creates_github_json_db_from_config():
    with patch("platzky.db.github_json_db.Github") as MockGithub:
        mock_repo = MagicMock()
        mock_file = MagicMock()
        mock_file.content = "eyJrZXkiOiAidmFsdWUifQ=="
        mock_file.decoded_content = b'{"key": "value"}'
        MockGithub.return_value.get_repo.return_value = mock_repo
        mock_repo.get_contents.return_value = mock_file

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
        assert db.data == {"key": "value"}


def test_creates_github_json_db_with_validated_config():
    with patch("platzky.db.github_json_db.Github") as MockGithub:
        mock_repo = MagicMock()
        mock_file = MagicMock()
        mock_file.content = "eyJrZXkiOiAidmFsdWUifQ=="
        mock_file.decoded_content = b'{"key": "value"}'
        MockGithub.return_value.get_repo.return_value = mock_repo
        mock_repo.get_contents.return_value = mock_file

        config = {
            "TYPE": "github_json_db",
            "GITHUB_TOKEN": "fake_token",
            "REPO_NAME": "fake_repo",
            "PATH_TO_FILE": "path/to/file.json",
            "BRANCH_NAME": "main",
        }
        db = get_db(config)
        assert isinstance(db, GithubJsonDb)
        assert db.branch_name == "main"
        assert db.file_path == "path/to/file.json"
        assert db.data == {"key": "value"}


def test_retrieves_data_from_github_file():
    with patch("platzky.db.github_json_db.Github") as MockGithub:
        mock_repo = MagicMock()
        mock_file = MagicMock()
        mock_file.content = "eyJrZXkiOiAidmFsdWUifQ=="  # Base64 for '{"key": "value"}'
        mock_file.decoded_content = b'{"key": "value"}'
        MockGithub.return_value.get_repo.return_value = mock_repo
        mock_repo.get_contents.return_value = mock_file

        db = GithubJsonDb("fake_token", "fake_repo", "main", "path/to/file.json")
        assert db.data == {"key": "value"}


def test_raises_error_for_directory_path():
    with patch("platzky.db.github_json_db.Github") as MockGithub:
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = [MagicMock()]  # Simulate directory
        MockGithub.return_value.get_repo.return_value = mock_repo

        with pytest.raises(
            ValueError, match="Path 'path/to/file.json' points to a directory, not a file"
        ):
            GithubJsonDb("fake_token", "fake_repo", "main", "path/to/file.json")


def test_retrieves_data_via_download_url_when_content_is_empty():
    with (
        patch("platzky.db.github_json_db.Github") as MockGithub,
        patch("platzky.db.github_json_db.requests.get") as mock_requests,
    ):
        mock_repo = MagicMock()
        mock_file = MagicMock()
        mock_file.content = None
        mock_file.download_url = "https://example.com/file.json"
        mock_repo.get_contents.return_value = mock_file
        MockGithub.return_value.get_repo.return_value = mock_repo

        mock_response = MagicMock()
        mock_response.text = '{"key": "value"}'
        mock_requests.return_value = mock_response

        db = GithubJsonDb("fake_token", "fake_repo", "main", "path/to/file.json")
        assert db.data == {"key": "value"}


def test_raises_error_for_invalid_json_content():
    with patch("platzky.db.github_json_db.Github") as MockGithub:
        mock_repo = MagicMock()
        mock_file = MagicMock()
        mock_file.content = "eyJrZXkiOiAidmFsdWUifQ=="  # Base64 for '{"key": "value"}'
        mock_file.decoded_content = b"invalid json"
        mock_repo.get_contents.return_value = mock_file
        MockGithub.return_value.get_repo.return_value = mock_repo

        with pytest.raises(ValueError, match="Error retrieving or processing GitHub content"):
            GithubJsonDb("fake_token", "fake_repo", "main", "path/to/file.json")
