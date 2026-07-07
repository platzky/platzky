from unittest.mock import MagicMock, patch

import pytest

from platzky.db.google_json_db import get_blob


class TestGoogleJsonDb:
    @pytest.fixture
    def mock_client(self):
        with patch("platzky.db.google_json_db.Client") as mock_client:
            yield mock_client

    def test_get_blob(self, mock_client: MagicMock):
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
