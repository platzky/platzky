"""Google Cloud Storage-based JSON database implementation."""

import json
from typing import Any

from google.cloud.storage import Client
from pydantic import Field

from platzky.db.db import DBConfig
from platzky.db.json_db import Json


def db_config_type() -> type["GoogleJsonDbConfig"]:
    """Return the configuration class for Google Cloud Storage JSON database."""
    return GoogleJsonDbConfig


class GoogleJsonDbConfig(DBConfig):
    """Configuration for Google Cloud Storage JSON database connection."""

    bucket_name: str = Field(alias="BUCKET_NAME")
    source_blob_name: str = Field(alias="SOURCE_BLOB_NAME")


def db_from_config(config: GoogleJsonDbConfig) -> "GoogleJsonDb":
    """Create a Google Cloud Storage JSON database instance from configuration."""
    return GoogleJsonDb(config.bucket_name, config.source_blob_name)


def get_db(config: dict[str, Any]) -> "GoogleJsonDb":
    """Get a Google Cloud Storage JSON database instance from raw configuration."""
    google_json_db_config = GoogleJsonDbConfig.model_validate(config)
    return GoogleJsonDb(google_json_db_config.bucket_name, google_json_db_config.source_blob_name)


def get_blob(bucket_name: str, source_blob_name: str) -> Any:
    """Retrieve a blob from Google Cloud Storage."""
    storage_client = Client()
    bucket = storage_client.bucket(bucket_name)
    return bucket.blob(source_blob_name)


def get_data(blob: Any) -> dict[str, Any]:
    """Download and parse JSON data from a blob."""
    raw_data = blob.download_as_text()
    return json.loads(raw_data)


class GoogleJsonDb(Json):
    """JSON database stored in Google Cloud Storage."""

    def __init__(self, bucket_name: str, source_blob_name: str) -> None:
        """Initialize Google Cloud Storage JSON database connection."""
        self.bucket_name = bucket_name
        self.source_blob_name = source_blob_name

        self.blob = get_blob(self.bucket_name, self.source_blob_name)
        data = get_data(self.blob)
        super().__init__(data)

        self.module_name = "google_json_db"
        self.db_name = "GoogleJsonDb"
