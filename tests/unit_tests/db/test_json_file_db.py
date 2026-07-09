import json
from datetime import datetime
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from platzky.db.json_file_db import JsonFile, JsonFileDbConfig, db_from_config


class TestJsonFileDb:
    @pytest.fixture
    def sample_data(self) -> dict[str, object]:
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
    def mock_file_path(self) -> str:
        return "/mock/path/to/data.json"

    def test_init_loads_data(self, sample_data: dict[str, object], mock_file_path: str):
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)):
            db = JsonFile(mock_file_path)
            assert db.data == sample_data
            assert db.module_name == "json_file_db"
            assert db.db_name == "JsonFileDb"

    def test_get_app_description(self, sample_data: dict[str, object], mock_file_path: str):
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)):
            db = JsonFile(mock_file_path)
            assert db.get_app_description("en") == "English description"
            assert db.get_app_description("de") == "Deutsche Beschreibung"
            assert db.get_app_description("fr") == ""

    def test_add_comment_saves_file(self, sample_data: dict[str, object], tmp_path: Path):
        data_file = tmp_path / "data.json"
        data_file.write_text(json.dumps(sample_data))

        test_date = datetime(2023, 2, 1, 10, 0)
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = test_date
            db = JsonFile(str(data_file))
            db.add_comment("Test User", "New comment", "post-1")

        # Verify the comment was added to the db's data structure
        comments = db.data["site_content"]["posts"][0]["comments"]
        assert len(comments) == 1
        assert comments[0]["author"] == "Test User"
        assert comments[0]["comment"] == "New comment"
        assert comments[0]["date"] == "2023-02-01T10:00:00"

        # Verify it was actually persisted to disk (not just kept in memory)
        persisted = json.loads(data_file.read_text())
        persisted_comments = persisted["site_content"]["posts"][0]["comments"]
        assert len(persisted_comments) == 1
        assert persisted_comments[0]["author"] == "Test User"

    def test_init_file_not_found(self, mock_file_path: str):
        with (
            patch("builtins.open", side_effect=FileNotFoundError),
            pytest.raises(FileNotFoundError),
        ):
            JsonFile(mock_file_path)

    def test_malformed_json_file(self, mock_file_path: str):
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

    def test_db_from_config(self, sample_data: dict[str, object], mock_file_path: str):
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)):
            config = JsonFileDbConfig(TYPE="json_file", PATH=mock_file_path)
            db = db_from_config(config)
            assert isinstance(db, JsonFile)
            assert db.data_file_path == mock_file_path

    def test_get_all_posts(self, sample_data: dict[str, object], mock_file_path: str):
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)):
            db = JsonFile(mock_file_path)
            posts = db.get_all_posts("en")
            assert len(posts) == 1
            assert posts[0].title == "Post 1"
            assert posts[0].slug == "post-1"

    def test_get_post(self, sample_data: dict[str, object], mock_file_path: str):
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)):
            db = JsonFile(mock_file_path)
            post = db.get_post("post-1")
            assert post.title == "Post 1"
            assert post.slug == "post-1"

    def test_get_post_not_found(self, sample_data: dict[str, object], mock_file_path: str):
        json_str = json.dumps(sample_data)
        with patch("builtins.open", mock_open(read_data=json_str)), pytest.raises(ValueError):
            db = JsonFile(mock_file_path)
            db.get_post("non-existent")
