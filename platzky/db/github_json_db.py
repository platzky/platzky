"""GitHub-based JSON database implementation."""

import json
from typing import Any

import requests
from github import Github
from pydantic import Field

from platzky.db.db import DBConfig
from platzky.db.json_db import Json as JsonDB


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


def get_db(config: dict[str, Any]) -> "GithubJsonDb":
    """Get a GitHub JSON database instance from raw configuration.

    Args:
        config: Raw configuration dictionary

    Returns:
        Configured GitHub JSON database instance
    """
    return db_from_config(GithubJsonDbConfig.model_validate(config))


class GithubJsonDb(JsonDB):
    """JSON database stored in a GitHub repository."""

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
        self.repo = Github(github_token).get_repo(repo_name)
        self.file_path = path_to_file

        try:
            file_content = self.repo.get_contents(self.file_path, ref=self.branch_name)

            if isinstance(file_content, list):
                raise ValueError(f"Path '{self.file_path}' points to a directory, not a file")

            if file_content.content:
                raw_data = file_content.decoded_content.decode("utf-8")
            else:

                download_url = file_content.download_url
                response = requests.get(download_url, timeout=40)
                response.raise_for_status()
                raw_data = response.text

            self.data = json.loads(raw_data)

        except (json.JSONDecodeError, requests.RequestException) as e:
            raise ValueError(f"Error parsing JSON content: {e}")
        except Exception as e:
            raise ValueError(f"Error retrieving GitHub content: {e}")

        super().__init__(self.data)

        self.module_name = "github_json_db"
        self.db_name = "GithubJsonDb"
