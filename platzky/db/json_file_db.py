"""Local file-based JSON database implementation."""

import json
from typing import Any

from pydantic import Field

from platzky.db.db import DBConfig
from platzky.db.json_db import Json


def db_config_type() -> type["JsonFileDbConfig"]:
    """Return the configuration class for JSON file database."""
    return JsonFileDbConfig


class JsonFileDbConfig(DBConfig):
    """Configuration for JSON file database."""

    path: str = Field(alias="PATH")


def get_db(config: dict[str, Any]) -> "JsonFile":
    """Get a JSON file database instance from raw configuration."""
    json_file_db_config = JsonFileDbConfig.model_validate(config)
    return JsonFile(json_file_db_config.path)


def db_from_config(config: JsonFileDbConfig) -> "JsonFile":
    """Create a JSON file database instance from configuration."""
    return JsonFile(config.path)


class JsonFile(Json):
    """JSON database stored in a local file with read/write support."""

    def __init__(self, path: str) -> None:
        """Initialize JSON file database from a local file path."""
        self.data_file_path = path
        with open(self.data_file_path) as json_file:
            data = json.load(json_file)
            super().__init__(data)
        self.module_name = "json_file_db"
        self.db_name = "JsonFileDb"

    def __save_file(self) -> None:
        with open(self.data_file_path, "w") as json_file:
            json.dump(self.data, json_file)

    def add_comment(self, author_name: str, comment: str, post_slug: str) -> None:
        """Add a comment to a blog post and persist to file."""
        super().add_comment(author_name, comment, post_slug)
        self.__save_file()
