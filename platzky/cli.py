"""Command line interface for running a Platzky application."""

import json
from importlib.resources import files
from pathlib import Path
from secrets import token_hex
from string import Template

import click

from platzky.db.exceptions import InvalidSiteContentError
from platzky.db.json_db import validate_json_site_content
from platzky.platzky import create_app

_TARGET_CONFIG_FILENAME = "config.yml"
_TARGET_DATA_FILENAME = "data.json"
_SCAFFOLD_DIR = "scaffold"
_CONFIG_FILE_MODE = 0o600
_CONFIG_TEMPLATE = "config.template.yml"
_DATA_TEMPLATE = "data.template.json"


def _render_scaffold(filename: str, **values: str) -> str:
    """Fill in the placeholders of a scaffold file shipped with the package.

    Args:
        filename: Name of the file in the scaffold directory
        values: Replacements for the file's ``$placeholder`` markers

    Returns:
        Contents of the file with every placeholder replaced
    """
    scaffold_file = files("platzky").joinpath(_SCAFFOLD_DIR).joinpath(filename)
    return Template(scaffold_file.read_text(encoding="utf-8")).substitute(values)


@click.group()
def cli() -> None:
    """Platzky command line interface."""


@cli.command()
@click.option("--config", "config_path", required=True, help="Path to the YAML config file.")
@click.option("--host", default="127.0.0.1", show_default=True, help="Interface to bind to.")
@click.option("--port", default=5000, show_default=True, type=int, help="Port to bind to.")
def run(config_path: str, host: str, port: int) -> None:
    """Run the development server, with the reloader, the debugger and fake login available."""
    app = create_app(config_path, development=True)
    # Explicit debug wins over FLASK_DEBUG, which Flask.run would otherwise let override it.
    app.run(host=host, port=port, debug=True)


@cli.command()
@click.option(
    "--path",
    "directory",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory the files are created in.",
)
def init(directory: Path) -> None:
    """Write a config file and a JSON database with sample content, ready to run."""
    directory.mkdir(parents=True, exist_ok=True)
    config_file, data_file = directory / _TARGET_CONFIG_FILENAME, directory / _TARGET_DATA_FILENAME
    existing = [str(f) for f in (config_file, data_file) if f.exists()]
    if existing:
        raise click.ClickException(f"Refusing to overwrite: {', '.join(existing)}")

    # Created owner-only (0600) before anything is written, so the generated SECRET_KEY is never
    # briefly world-readable. The key signs session cookies: whoever reads it can forge a login,
    # and on a shared host every other local user could read a file left at the default mode.
    config_file.touch(mode=_CONFIG_FILE_MODE)
    config_file.write_text(
        _render_scaffold(_CONFIG_TEMPLATE, secret_key=token_hex(32)),
        encoding="utf-8",
    )
    data_file.write_text(_render_scaffold(_DATA_TEMPLATE), encoding="utf-8")
    click.echo(f"Created {config_file} and {data_file}")
    # From that directory, because the database path in the config is relative to it.
    click.echo(f"Run it from {directory.resolve()}: platzky run --config {_TARGET_CONFIG_FILENAME}")
    click.echo("It starts with one sample post and an About page; edit them in the database file.")


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def check(file: Path) -> None:
    """Validate the site configuration in a JSON database FILE.

    Checks the site-configuration part of ``site_content`` (texts, theme, per-language content);
    the blog index meta is checked too; posts and pages are not. Prints OK and exits 0 when it
    is valid; otherwise lists every problem with its path and exits 1.
    """
    try:
        document = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise click.ClickException(f"{file} cannot be read as JSON: {error}") from error
    if not isinstance(document, dict):
        raise click.ClickException(f"{file} is not a JSON object")
    try:
        validate_json_site_content(document.get("site_content"))
    except InvalidSiteContentError as error:
        raise click.ClickException(str(error)) from error
    click.echo("OK")
