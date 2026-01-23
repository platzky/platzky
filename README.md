![Github Actions](https://github.com/platzky/platzky/actions/workflows/tests.yml/badge.svg?event=push&branch=main)
[![Coverage Status](https://coveralls.io/repos/github/platzky/platzky/badge.svg?branch=main)](https://coveralls.io/github/platzky/platzky?branch=main)
[![Documentation](https://readthedocs.org/projects/platzky/badge/?version=latest)](https://platzky.readthedocs.io/)
[![PyPI version](https://badge.fury.io/py/platzky.svg)](https://pypi.org/project/platzky/)

# Platzky

Platzky is a lightweight web application engine built on Flask that provides a simple and easy way to create and run web applications in Python.

## Features

- **Multi-language support** - Automatic locale detection with per-domain language configuration
- **Pluggable database backends** - JSON file, Google Cloud Storage, or MongoDB
- **Built-in blog module** - Ready-to-use blog functionality
- **SEO tools** - Automatic sitemap and robots.txt generation
- **Extensible plugin system** - Add custom functionality through plugins
- **OpenTelemetry integration** - Built-in observability and tracing support
- **Pydantic configuration** - Type-safe YAML configuration with validation

## Requirements

- Python 3.10 or higher

## Installation

```bash
pip install platzky
```

Or with Poetry:

```bash
poetry add platzky
```

## Quickstart

1. Create a configuration file `config.yml`:

```yaml
APP_NAME: My Platzky App
SECRET_KEY: change-this-to-something-secret

DB:
  TYPE: json_file
  PATH: data.json

LANGUAGES:
  en:
    name: English
    flag: uk
    country: GB
```

2. Run the application:

```bash
flask --app "platzky.platzky:create_app(config_path='config.yml')" run
```

3. Open http://127.0.0.1:5000 in your browser.

## Database Backends

Platzky supports multiple storage backends:

| Backend | Type | Use Case |
|---------|------|----------|
| JSON File | `json_file` | Development, small deployments |
| Google Cloud Storage | `google_hosted_json_file` | Google Cloud / App Engine |
| MongoDB | `mongodb` | Production, scalable deployments |

Example MongoDB configuration:

```yaml
DB:
  TYPE: mongodb
  CONNECTION_STRING: mongodb://localhost:27017/
  DATABASE_NAME: platzky
```

## Optional Features

Install with telemetry support:

```bash
pip install platzky[telemetry]
```

## Documentation

Full documentation is available at [platzky.readthedocs.io](https://platzky.readthedocs.io/).

- [Installation Guide](https://platzky.readthedocs.io/en/latest/installation.html)
- [Configuration Reference](https://platzky.readthedocs.io/en/latest/config.html)
- [Database Backends](https://platzky.readthedocs.io/en/latest/database.html)
- [API Reference](https://platzky.readthedocs.io/en/latest/api.html)

## Examples

For working examples, check the e2e tests in `tests/e2e` directory and the Makefile.

## License

MIT License - see [LICENSE](LICENSE) for details.
