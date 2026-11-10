import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner, Result

from platzky.cli import cli
from platzky.platzky import create_app


def test_run_starts_server_on_given_address():
    app = MagicMock()

    with patch("platzky.cli.create_app", return_value=app) as create:
        result = CliRunner().invoke(
            cli, ["run", "--config", "config.yml", "--host", "0.0.0.0", "--port", "8080"]
        )

    assert result.exit_code == 0
    create.assert_called_once_with("config.yml", development=True)
    app.run.assert_called_once_with(host="0.0.0.0", port=8080, debug=True)


def test_run_defaults_to_localhost():
    app = MagicMock()

    with patch("platzky.cli.create_app", return_value=app):
        result = CliRunner().invoke(cli, ["run", "--config", "config.yml"])

    assert result.exit_code == 0
    app.run.assert_called_once_with(host="127.0.0.1", port=5000, debug=True)


def test_run_requires_config():
    result = CliRunner().invoke(cli, ["run"])

    assert result.exit_code != 0
    assert "--config" in result.output


def test_run_is_development_regardless_of_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FLASK_DEBUG", "0")
    app = MagicMock()

    with patch("platzky.cli.create_app", return_value=app) as create:
        result = CliRunner().invoke(cli, ["run", "--config", "config.yml"])

    assert result.exit_code == 0
    create.assert_called_once_with("config.yml", development=True)
    assert app.run.call_args.kwargs["debug"] is True


def _init(directory: Path) -> Result:
    return CliRunner().invoke(cli, ["init", "--path", str(directory)])


class TestInit:
    def test_writes_config_and_database(self, tmp_path: Path):
        result = _init(tmp_path)

        assert result.exit_code == 0
        config = yaml.safe_load((tmp_path / "config.yml").read_text())
        assert config["APP_NAME"] == "My Platzky App"
        assert config["DB"] == {"TYPE": "json_file", "PATH": "data.json"}
        assert config["USE_WWW"] is False
        document = json.loads((tmp_path / "data.json").read_text())
        assert [post["slug"] for post in document["blog"]["posts"]] == ["hello-platzky"]
        assert [page["slug"] for page in document["blog"]["pages"]] == ["about"]
        assert document["site_config"]["localized_content"]["en"]["menu_items"] == [
            {"name": "Blog", "url": "/blog/"},
            {"name": "About", "url": "/blog/page/about"},
        ]

    def test_created_site_serves_its_sample_content(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _init(tmp_path)
        # DB PATH is relative, so the application runs from the directory it was created in.
        monkeypatch.chdir(tmp_path)

        app = create_app("config.yml")
        client = app.test_client()

        assert client.get("/blog/").status_code == 200
        assert client.get("/blog/hello-platzky").status_code == 200
        assert client.get("/blog/page/about").status_code == 200

    def test_tells_how_to_run_the_application(self, tmp_path: Path):
        result = _init(tmp_path)

        # The database path in the config is relative, so the directory matters.
        assert f"Run it from {tmp_path.resolve()}: platzky run --config config.yml" in result.output

    @pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
    def test_config_is_readable_only_by_its_owner(self, tmp_path: Path):
        _init(tmp_path)

        # It holds the generated SECRET_KEY, which signs session cookies.
        assert (tmp_path / "config.yml").stat().st_mode & 0o777 == 0o600

    def test_secret_key_differs_between_applications(self, tmp_path: Path):
        _init(tmp_path / "first")
        _init(tmp_path / "second")

        keys = {
            yaml.safe_load((tmp_path / name / "config.yml").read_text())["SECRET_KEY"]
            for name in ("first", "second")
        }
        assert len(keys) == 2

    def test_refuses_to_overwrite(self, tmp_path: Path):
        _init(tmp_path)
        config_file = tmp_path / "config.yml"
        config_file.write_text(config_file.read_text().replace("My Platzky App", "Edited By Hand"))

        result = _init(tmp_path)

        assert result.exit_code != 0
        assert "Refusing to overwrite" in result.output
        assert "Edited By Hand" in config_file.read_text()


def _check(tmp_path: Path, document: object) -> Result:
    data_file = tmp_path / "data.json"
    data_file.write_text(json.dumps(document), encoding="utf-8")
    return CliRunner().invoke(cli, ["check", str(data_file)])


class TestCheck:
    def test_valid_site_config_is_ok(self, tmp_path: Path):
        result = _check(
            tmp_path,
            {
                "site_config": {
                    "app_name": "Literature",
                    "localized_content": {"pl": {"home_page_path": "/blog/page/o-nas"}},
                },
                "blog": {"posts": [], "meta": {"pl": {"title": "Notatki"}}},
            },
        )

        assert (result.exit_code, result.output) == (0, "OK\n")

    def test_sample_database_created_by_init_is_ok(self, tmp_path: Path):
        _init(tmp_path)

        result = CliRunner().invoke(cli, ["check", str(tmp_path / "data.json")])

        assert (result.exit_code, result.output) == (0, "OK\n")

    def test_problems_are_listed_with_their_paths(self, tmp_path: Path):
        result = _check(
            tmp_path,
            {"blog": {"posts": None, "meta": {"pl": {"title": None}}}},
        )

        assert result.exit_code == 1
        assert result.output.splitlines() == [
            "Error: blog.posts: Input should be a valid tuple",
            "blog.meta.pl.title: Input should be a valid string",
        ]

    def test_file_that_is_not_json_is_an_error(self, tmp_path: Path):
        data_file = tmp_path / "data.json"
        data_file.write_text("{", encoding="utf-8")

        result = CliRunner().invoke(cli, ["check", str(data_file)])

        assert result.exit_code == 1
        assert result.output.startswith(f"Error: {data_file} cannot be read as JSON")

    def test_file_that_is_not_utf8_is_an_error(self, tmp_path: Path):
        data_file = tmp_path / "data.json"
        data_file.write_bytes(b"\xff\xfe{}")

        result = CliRunner().invoke(cli, ["check", str(data_file)])

        assert result.exit_code == 1
        assert result.output.startswith(f"Error: {data_file} cannot be read as JSON")

    def test_json_that_is_not_an_object_is_an_error(self, tmp_path: Path):
        result = _check(tmp_path, [])

        assert result.exit_code == 1
        assert result.output == f"Error: {tmp_path / 'data.json'} is not a JSON object\n"

    def test_missing_file_is_an_error(self, tmp_path: Path):
        result = CliRunner().invoke(cli, ["check", str(tmp_path / "absent.json")])

        assert result.exit_code == 2
