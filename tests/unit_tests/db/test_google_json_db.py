import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from platzky.db.google_json_db import GoogleJsonDb, get_blob, get_db


class TestGoogleJsonDb:
    @pytest.fixture
    def mock_client(self):
        with patch("platzky.db.google_json_db.Client") as mock_client:
            yield mock_client

    def test_get_db_function(self):
        """Test the get_db function that creates a GoogleJsonDb instance from config."""
        # Create a config dict with the correct format
        config_dict = {
            "TYPE": "google_json_db",
            "BUCKET_NAME": "test-bucket",
            "SOURCE_BLOB_NAME": "test-blob.json",
        }

        # Mock the blob data
        mock_blob = MagicMock()
        mock_blob.download_as_text.return_value = json.dumps({"test": "data"})

        # Mock the get_blob function
        with patch("platzky.db.google_json_db.get_blob") as mock_get_blob:
            mock_get_blob.return_value = mock_blob

            # Test that get_db returns a GoogleJsonDb instance
            db = get_db(config_dict)
            assert isinstance(db, GoogleJsonDb)
            assert db.bucket_name == "test-bucket"
            assert db.source_blob_name == "test-blob.json"

            # Verify that the data was loaded correctly
            assert db.data == {"test": "data"}

    def test_get_blob(self, mock_client: Any):
        """Test the get_blob function that retrieves a blob from Google Cloud Storage."""
        # Set up the mock
        mock_bucket = MagicMock()
        mock_client.return_value.bucket.return_value = mock_bucket
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        # Call the function
        result = get_blob("test-bucket", "test-blob.json")

        # Assert the mock was called correctly
        mock_client.return_value.bucket.assert_called_once_with("test-bucket")
        mock_bucket.blob.assert_called_once_with("test-blob.json")

        # Assert the result is the mock blob
        assert result == mock_blob
