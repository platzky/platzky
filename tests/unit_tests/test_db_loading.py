from platzky.config import Config
from platzky.db import db_loader
from unittest.mock import patch, mock_open, MagicMock


def test_loading_json_db_dynamically():
    config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "secret",
        "DB": {"TYPE": "json", "DATA": {}},
    }

    config = Config.model_validate(config_data)

    db = db_loader.get_db(config.db)
    assert db.__class__.__name__ == "Json"


def test_loading_json_file_db_dynamically():
    config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "secret",
        "DB": {
            "TYPE": "json_file",
            "PATH": "some/path",
        },
    }

    config = Config.model_validate(config_data)

    with patch("builtins.open", mock_open(read_data="data")):
        with patch("json.load", return_value={"site_content": {}}):
            db = db_loader.get_db(config.db)
            assert db.__class__.__name__ == "JsonFile"
            assert db.data == {"site_content": {}}


def test_loading_google_json_db_dynamically():
    config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "secret",
        "DB": {
            "TYPE": "google_json",
            "BUCKET_NAME": "bucket-name",
            "SOURCE_BLOB_NAME": "data.json",
        },
    }

    expected_data = {"site_content": {}}

    with patch("google.cloud.storage.Client") as mock_client:
        client_mock = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        client_mock.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.download_as_text.return_value = '{"site_content": {}}'

        mock_client.return_value = client_mock

        config = Config.model_validate(config_data)
        db = db_loader.get_db(config.db)

        assert db.__class__.__name__ == "GoogleJsonDb"
        assert db.data == expected_data

        mock_client.assert_called_once()
        mock_bucket.blob.assert_called_once_with("data.json")
        mock_blob.download_as_text.assert_called_once()


def test_loading_graph_db_dynamically():
    config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "secret",
        "DB": {
            "TYPE": "graph_ql",
            "CMS_ENDPOINT": "http://localhost:1337/graphql",
            "CMS_TOKEN": "token",
        },
    }

    config = Config.model_validate(config_data)
    db = db_loader.get_db(config.db)
    assert db.__class__.__name__ == "GraphQL"
