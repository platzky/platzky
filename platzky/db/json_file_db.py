"""Local file-based JSON database implementation."""

from pydantic import Field

from platzky.db.db import DBConfig
from platzky.db.json_db import Json
from platzky.db.stores import FileStore


def db_config_type() -> type["JsonFileDbConfig"]:
    """Return the configuration class for JSON file database.

    Returns:
        JsonFileDbConfig class
    """
    return JsonFileDbConfig


class JsonFileDbConfig(DBConfig):
    """Configuration for JSON file database."""

    path: str = Field(alias="PATH")


def db_from_config(config: JsonFileDbConfig) -> "JsonFile":
    """Create a JSON file database instance from configuration.

    Args:
        config: JSON file database configuration

    Returns:
        Configured JSON file database instance
    """
    return JsonFile(config.path)


class JsonFile(Json):
    """JSON database stored in a local file with read/write support.

    Writes are atomic (temp file + rename), see `platzky.db.stores.FileStore`.
    """

    def __init__(self, path: str) -> None:
        """Initialize JSON file database from a local file path.

        Args:
            path: Absolute or relative path to the JSON file
        """
        self.data_file_path = path
        super().__init__(store=FileStore(path))
        self.module_name = "json_file_db"
        self.db_name = "JsonFileDb"
