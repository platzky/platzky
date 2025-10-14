import json

from pydantic import Field

from platzky.db.db import DBConfig
from platzky.db.json_db import Json


def db_config_type():
    return JsonFileDbConfig


class JsonFileDbConfig(DBConfig):
    path: str = Field(alias="PATH")
    cache_ttl: float | None = Field(alias="CACHE_TTL", default=None)


def get_db(config):
    json_file_db_config = JsonFileDbConfig.model_validate(config)
    return JsonFile(json_file_db_config.path, json_file_db_config.cache_ttl)


def db_from_config(config: JsonFileDbConfig):
    return JsonFile(config.path, config.cache_ttl)


class JsonFile(Json):
    def __init__(self, path: str, cache_ttl=None):
        self.data_file_path = path
        with open(self.data_file_path) as json_file:
            data = json.load(json_file)
            super().__init__(data, cache_ttl)
        self.module_name = "json_file_db"
        self.db_name = "JsonFileDb"

    def refresh_cache(self) -> None:
        """Refresh the cached data from the file."""
        with open(self.data_file_path) as json_file:
            self.data = json.load(json_file)
        super().refresh_cache()

    def __save_file(self):
        with open(self.data_file_path, "w") as json_file:
            json.dump(self.data, json_file)

    def add_comment(self, author_name, comment, post_slug):
        super().add_comment(author_name, comment, post_slug)
        self.__save_file()
