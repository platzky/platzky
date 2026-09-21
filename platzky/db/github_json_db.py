"""GitHub-based JSON database implementation."""

import base64
import json
from urllib.parse import quote

import requests
from pydantic import Field

from platzky.db.db import DBConfig
from platzky.db.json_db import Json as JsonDB
from platzky.db.json_stores import ReadOnlyStore


def db_config_type() -> type["GithubJsonDbConfig"]:
    """Return the configuration class for GitHub JSON database.

    Returns:
        GithubJsonDbConfig class
    """
    return GithubJsonDbConfig


class GithubJsonDbConfig(DBConfig):
    """Configuration for GitHub JSON database connection."""

    github_token: str = Field(alias="GITHUB_TOKEN")
    repo_name: str = Field(alias="REPO_NAME")
    path_to_file: str = Field(alias="PATH_TO_FILE")
    branch_name: str = Field(alias="BRANCH_NAME", default="main")


def db_from_config(config: GithubJsonDbConfig) -> "GithubJsonDb":
    """Create a GitHub JSON database instance from configuration.

    Args:
        config: GitHub JSON database configuration

    Returns:
        Configured GitHub JSON database instance
    """
    return GithubJsonDb(
        config.github_token, config.repo_name, config.branch_name, config.path_to_file
    )


class GithubJsonDb(JsonDB):
    """JSON database stored in a GitHub repository.

    Read-only: the file is fetched once at construction time; writes raise
    `platzky.db.exceptions.ReadOnlyStorageError`.
    """

    def __init__(
        self, github_token: str, repo_name: str, branch_name: str, path_to_file: str
    ) -> None:
        """Initialize GitHub JSON database connection.

        Args:
            github_token: GitHub personal access token
            repo_name: Full repository name (e.g., 'owner/repo')
            branch_name: Branch name to read from
            path_to_file: Path to the JSON file within the repository
        """
        self.branch_name = branch_name
        self.file_path = path_to_file

        try:
            response = requests.get(
                f"https://api.github.com/repos/{repo_name}/contents/{quote(self.file_path)}",
                params={"ref": self.branch_name},
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=40,
            )
            response.raise_for_status()
            file_content = response.json()

            if isinstance(file_content, list):
                raise ValueError(f"Path '{self.file_path}' points to a directory, not a file")

            if file_content.get("content"):
                raw_data = base64.b64decode(file_content["content"]).decode("utf-8")
            else:
                download_response = requests.get(file_content["download_url"], timeout=40)
                download_response.raise_for_status()
                raw_data = download_response.text

            self.data = json.loads(raw_data)

        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing JSON content: {e}")
        except Exception as e:
            raise ValueError(f"Error retrieving GitHub content: {e}")

        super().__init__(store=ReadOnlyStore(self.data))

        self.module_name = "github_json_db"
        self.db_name = "GithubJsonDb"
