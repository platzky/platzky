import json
from datetime import datetime
from unittest.mock import mock_open, patch

import pytest

from platzky.db.json_file_db import JsonFile, JsonFileDbConfig, db_from_config, get_db


class TestJsonFileDb:
    @pytest.fixture
    def sample_data(self):
        return {
            "site_content": {
                "app_description": {"en": "English description", "de": "Deutsche Beschreibung"},
                "posts": [
                    {
                        "title": "Post 1",
                        "slug": "post-1",
                        "content": "Post content",
                        "author": "Author 1",
                        "contentInMarkdown": "# Post 1",
                        "excerpt": "Post 1 excerpt",
                        "comments": [],
                        "tags": ["tag1", "tag2"],
                        "language": "en",
                        "coverImage": {"url": "/images/post1.jpg"},
                        "date": "2023-01-01T00:00:00",
                    }
                ],
                "logo_url": "/logo.png",
            }
        }

    @pytest.fixture
    def mock_file_path(self):
        return "/mock/path/to/data.json"

    def test_init_loads_data(self, sample_data, mock_file_path):
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)):
            db = JsonFile(mock_file_path)
            assert db.data == sample_data
            assert db.module_name == "json_file_db"
            assert db.db_name == "JsonFileDb"

    def test_get_app_description(self, sample_data, mock_file_path):
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)):
            db = JsonFile(mock_file_path)
            assert db.get_app_description("en") == "English description"
            assert db.get_app_description("de") == "Deutsche Beschreibung"
            assert db.get_app_description("fr") is None

    def test_add_comment_saves_file(self, sample_data, mock_file_path):
        json_str = json.dumps(sample_data)
        mock_file = mock_open(read_data=json_str)

        test_date = datetime(2023, 2, 1, 10, 0)
        with patch("builtins.open", mock_file), patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = test_date
            db = JsonFile(mock_file_path)
            db.add_comment("Test User", "New comment", "post-1")

        # Check that the file was opened for writing
        mock_file.assert_called_with(mock_file_path, "w")

        # Instead of parsing the written data, check if write was called
        # and verify the expected data is in the updated db object
        assert mock_file().write.called

        # Verify the comment was added to the db's data structure
        comments = db.data["site_content"]["posts"][0]["comments"]
        assert len(comments) == 1
        assert comments[0]["author"] == "Test User"
        assert comments[0]["comment"] == "New comment"
        assert comments[0]["date"] == "2023-02-01T10:00:00"

    def test_init_file_not_found(self, mock_file_path):
        with (
            patch("builtins.open", side_effect=FileNotFoundError),
            pytest.raises(FileNotFoundError),
        ):
            JsonFile(mock_file_path)

    def test_malformed_json_file(self, mock_file_path):
        with (
            patch("builtins.open", mock_open(read_data="This is not valid JSON")),
            pytest.raises(json.JSONDecodeError),
        ):
            JsonFile(mock_file_path)

    def test_json_file_db_config(self):
        config_dict = {"PATH": "/path/to/data.json", "TYPE": "json_file"}
        config = JsonFileDbConfig.model_validate(config_dict)
        assert config.path == "/path/to/data.json"
        assert config.type == "json_file"

    def test_get_db(self, sample_data, mock_file_path):
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)):
            config = {"PATH": mock_file_path, "TYPE": "json_file"}
            db = get_db(config)
            assert isinstance(db, JsonFile)
            assert db.data_file_path == mock_file_path

    def test_db_from_config(self, sample_data, mock_file_path):
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)):
            config = JsonFileDbConfig(TYPE="json_file_db", PATH=mock_file_path)
            db = db_from_config(config)
            assert isinstance(db, JsonFile)
            assert db.data_file_path == mock_file_path

    def test_get_all_posts(self, sample_data, mock_file_path):
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)):
            db = JsonFile(mock_file_path)
            posts = db.get_all_posts("en")
            assert len(posts) == 1
            assert posts[0].title == "Post 1"
            assert posts[0].slug == "post-1"

    def test_get_post(self, sample_data, mock_file_path):
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)):
            db = JsonFile(mock_file_path)
            post = db.get_post("post-1")
            assert post.title == "Post 1"
            assert post.slug == "post-1"

    def test_get_post_not_found(self, sample_data, mock_file_path):
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)), pytest.raises(ValueError):
            db = JsonFile(mock_file_path)
            db.get_post("non-existent")
