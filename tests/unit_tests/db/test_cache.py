"""Tests for cache TTL and manual invalidation functionality."""

import json
import time
from unittest.mock import MagicMock, mock_open, patch

import pytest

from platzky.db.github_json_db import GithubJsonDb
from platzky.db.google_json_db import GoogleJsonDb
from platzky.db.json_db import Json
from platzky.db.json_file_db import JsonFile


class TestJsonDbCacheTTL:
    """Test cache TTL functionality for Json DB."""

    @pytest.fixture
    def sample_data(self):
        return {
            "site_content": {
                "app_description": {"en": "English description"},
                "posts": [],
            }
        }

    def test_cache_without_ttl_never_expires(self, sample_data):
        """Test that cache without TTL never expires."""
        db = Json(sample_data)

        # Cache should not be stale even after some time
        assert not db._is_cache_stale()
        assert db._cache_timestamp is None
        assert db.cache_ttl is None

    def test_cache_with_ttl_not_stale_initially(self, sample_data):
        """Test that cache with TTL is not stale immediately after creation."""
        db = Json(sample_data, cache_ttl=60)

        # Cache should not be stale immediately
        assert not db._is_cache_stale()
        assert db._cache_timestamp is not None
        assert db.cache_ttl == 60

    def test_cache_with_ttl_becomes_stale(self, sample_data):
        """Test that cache with TTL becomes stale after expiration."""
        db = Json(sample_data, cache_ttl=0.1)  # 0.1 seconds TTL

        # Cache should not be stale immediately
        assert not db._is_cache_stale()

        # Wait for cache to expire
        time.sleep(0.15)

        # Cache should now be stale
        assert db._is_cache_stale()

    def test_manual_refresh_updates_timestamp(self, sample_data):
        """Test that manual refresh updates the cache timestamp."""
        db = Json(sample_data, cache_ttl=60)

        original_timestamp = db._cache_timestamp
        time.sleep(0.01)  # Small delay

        db.refresh_cache()

        # Timestamp should be updated
        assert db._cache_timestamp > original_timestamp

    def test_get_site_content_auto_refreshes_on_ttl_expiration(self, sample_data):
        """Test that _get_site_content auto-refreshes when cache expires."""
        db = Json(sample_data, cache_ttl=0.1)

        original_timestamp = db._cache_timestamp

        # Wait for cache to expire
        time.sleep(0.15)

        # Access site content should trigger refresh
        content = db._get_site_content()

        # Timestamp should be updated
        assert db._cache_timestamp > original_timestamp
        assert content is not None

    def test_backward_compatibility_default_no_ttl(self, sample_data):
        """Test backward compatibility - default behavior has no TTL."""
        # Creating DB without cache_ttl parameter should work as before
        db = Json(sample_data)

        assert db.cache_ttl is None
        assert db._cache_timestamp is None
        assert not db._is_cache_stale()


class TestJsonFileDbCacheTTL:
    """Test cache TTL functionality for JsonFile DB."""

    @pytest.fixture
    def sample_data(self):
        return {
            "site_content": {
                "app_description": {"en": "English description"},
                "posts": [],
            }
        }

    @pytest.fixture
    def mock_file_path(self):
        return "/mock/path/to/data.json"

    def test_jsonfile_without_ttl(self, sample_data, mock_file_path):
        """Test JsonFile without TTL behaves as before."""
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)):
            db = JsonFile(mock_file_path)

            assert db.cache_ttl is None
            assert db._cache_timestamp is None

    def test_jsonfile_with_ttl(self, sample_data, mock_file_path):
        """Test JsonFile with TTL."""
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)):
            db = JsonFile(mock_file_path, cache_ttl=60)

            assert db.cache_ttl == 60
            assert db._cache_timestamp is not None

    def test_jsonfile_manual_refresh(self, sample_data, mock_file_path):
        """Test JsonFile manual cache refresh."""
        json_str = json.dumps(sample_data)
        mock_file = mock_open(read_data=json_str)

        with patch("builtins.open", mock_file):
            db = JsonFile(mock_file_path, cache_ttl=60)
            original_timestamp = db._cache_timestamp
            time.sleep(0.01)

            # Manually refresh cache
            db.refresh_cache()

            # Timestamp should be updated
            assert db._cache_timestamp > original_timestamp
            # File should have been read again
            assert mock_file.call_count >= 2  # Initial load + refresh

    def test_jsonfile_auto_refresh_on_ttl_expiration(self, sample_data, mock_file_path):
        """Test JsonFile auto-refreshes on TTL expiration."""
        initial_data = {
            "site_content": {
                "app_description": {"en": "Initial description"},
            }
        }
        updated_data = {
            "site_content": {
                "app_description": {"en": "Updated description"},
            }
        }

        json_str_initial = json.dumps(initial_data)
        json_str_updated = json.dumps(updated_data)

        # Create a mock that returns different data on subsequent calls
        mock_file = mock_open(read_data=json_str_initial)
        mock_file.return_value.read.side_effect = [json_str_initial, json_str_updated]

        with patch("builtins.open", mock_open(read_data=json_str_initial)):
            db = JsonFile(mock_file_path, cache_ttl=0.1)

            # Initial description
            content1 = db._get_site_content()
            assert content1["app_description"]["en"] == "Initial description"

            # Wait for TTL to expire
            time.sleep(0.15)

        # Mock the file to return updated data on next read
        with patch("builtins.open", mock_open(read_data=json_str_updated)):
            # Access should trigger auto-refresh
            content2 = db._get_site_content()
            assert content2["app_description"]["en"] == "Updated description"


class TestGoogleJsonDbCacheTTL:
    """Test cache TTL functionality for GoogleJsonDb."""

    def test_google_json_db_without_ttl(self):
        """Test GoogleJsonDb without TTL behaves as before."""
        with patch("platzky.db.google_json_db.get_blob") as mock_get_blob:
            mock_blob = MagicMock()
            mock_blob.download_as_text.return_value = json.dumps({"test": "data"})
            mock_get_blob.return_value = mock_blob

            db = GoogleJsonDb("test-bucket", "test-blob.json")

            assert db.cache_ttl is None
            assert db._cache_timestamp is None

    def test_google_json_db_with_ttl(self):
        """Test GoogleJsonDb with TTL."""
        with patch("platzky.db.google_json_db.get_blob") as mock_get_blob:
            mock_blob = MagicMock()
            mock_blob.download_as_text.return_value = json.dumps({"test": "data"})
            mock_get_blob.return_value = mock_blob

            db = GoogleJsonDb("test-bucket", "test-blob.json", cache_ttl=60)

            assert db.cache_ttl == 60
            assert db._cache_timestamp is not None

    def test_google_json_db_manual_refresh(self):
        """Test GoogleJsonDb manual cache refresh."""
        with patch("platzky.db.google_json_db.get_blob") as mock_get_blob:
            mock_blob = MagicMock()
            mock_blob.download_as_text.return_value = json.dumps({"test": "data"})
            mock_get_blob.return_value = mock_blob

            db = GoogleJsonDb("test-bucket", "test-blob.json", cache_ttl=60)
            original_timestamp = db._cache_timestamp
            time.sleep(0.01)

            # Manually refresh cache
            db.refresh_cache()

            # Timestamp should be updated
            assert db._cache_timestamp > original_timestamp
            # Blob should have been read again
            assert mock_blob.download_as_text.call_count == 2  # Initial + refresh


class TestGithubJsonDbCacheTTL:
    """Test cache TTL functionality for GithubJsonDb."""

    @pytest.fixture
    def mock_github_setup(self):
        """Setup mocks for GitHub API."""
        with patch("platzky.db.github_json_db.Github") as mock_github_class:
            # Setup GitHub mock
            mock_github = MagicMock()
            mock_repo = MagicMock()
            mock_file_content = MagicMock()
            mock_file_content.content = b'{"test": "data"}'
            mock_file_content.decoded_content = b'{"test": "data"}'

            mock_github_class.return_value = mock_github
            mock_github.get_repo.return_value = mock_repo
            mock_repo.get_contents.return_value = mock_file_content

            yield {
                "mock_github": mock_github,
                "mock_repo": mock_repo,
                "mock_file_content": mock_file_content,
            }

    def test_github_json_db_without_ttl(self, mock_github_setup):
        """Test GithubJsonDb without TTL behaves as before."""
        db = GithubJsonDb("token", "repo", "main", "path/to/file.json")

        assert db.cache_ttl is None
        assert db._cache_timestamp is None

    def test_github_json_db_with_ttl(self, mock_github_setup):
        """Test GithubJsonDb with TTL."""
        db = GithubJsonDb("token", "repo", "main", "path/to/file.json", cache_ttl=60)

        assert db.cache_ttl == 60
        assert db._cache_timestamp is not None

    def test_github_json_db_manual_refresh(self, mock_github_setup):
        """Test GithubJsonDb manual cache refresh."""
        db = GithubJsonDb("token", "repo", "main", "path/to/file.json", cache_ttl=60)
        original_timestamp = db._cache_timestamp
        time.sleep(0.01)

        # Manually refresh cache
        db.refresh_cache()

        # Timestamp should be updated
        assert db._cache_timestamp > original_timestamp
        # GitHub API should have been called again
        mock_repo = mock_github_setup["mock_repo"]
        assert mock_repo.get_contents.call_count == 2  # Initial + refresh


class TestCacheConfigIntegration:
    """Test cache configuration through config objects."""

    def test_google_json_db_config_with_cache_ttl(self):
        """Test GoogleJsonDb config with cache_ttl."""
        from platzky.db.google_json_db import GoogleJsonDbConfig, db_from_config

        with patch("platzky.db.google_json_db.get_blob") as mock_get_blob:
            mock_blob = MagicMock()
            mock_blob.download_as_text.return_value = json.dumps({"test": "data"})
            mock_get_blob.return_value = mock_blob

            config = GoogleJsonDbConfig(
                TYPE="google_json_db",
                BUCKET_NAME="test-bucket",
                SOURCE_BLOB_NAME="test-blob.json",
                CACHE_TTL=120,
            )

            db = db_from_config(config)

            assert db.cache_ttl == 120
            assert db._cache_timestamp is not None

    def test_json_file_db_config_with_cache_ttl(self):
        """Test JsonFile config with cache_ttl."""
        from platzky.db.json_file_db import JsonFileDbConfig, db_from_config

        json_str = json.dumps({"site_content": {}})
        with patch("builtins.open", mock_open(read_data=json_str)):
            config = JsonFileDbConfig(
                TYPE="json_file",
                PATH="/path/to/file.json",
                CACHE_TTL=90,
            )

            db = db_from_config(config)

            assert db.cache_ttl == 90
            assert db._cache_timestamp is not None

    def test_github_json_db_config_with_cache_ttl(self):
        """Test GithubJsonDb config with cache_ttl."""
        from platzky.db.github_json_db import GithubJsonDbConfig, db_from_config

        with (patch("platzky.db.github_json_db.Github") as mock_github_class,):
            # Setup GitHub mock
            mock_github = MagicMock()
            mock_repo = MagicMock()
            mock_file_content = MagicMock()
            mock_file_content.content = b'{"test": "data"}'
            mock_file_content.decoded_content = b'{"test": "data"}'

            mock_github_class.return_value = mock_github
            mock_github.get_repo.return_value = mock_repo
            mock_repo.get_contents.return_value = mock_file_content

            config = GithubJsonDbConfig(
                TYPE="github_json_db",
                GITHUB_TOKEN="token",
                REPO_NAME="repo",
                PATH_TO_FILE="path/to/file.json",
                BRANCH_NAME="main",
                CACHE_TTL=150,
            )

            db = db_from_config(config)

            assert db.cache_ttl == 150
            assert db._cache_timestamp is not None
