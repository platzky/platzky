![Github Actions](https://github.com/platzky/platzky/actions/workflows/tests.yml/badge.svg?event=push&branch=main)
[![Coverage Status](https://coveralls.io/repos/github/platzky/platzky/badge.svg?branch=main)](https://coveralls.io/github/platzky/platzky?branch=main)

# platzky

Platzky is engine which aims to provide simple and easy way to create and run web applications in python.

# How to use?

1. Install platzky with your favorite dependency management tool (`pip install platzky` or `poetry add platzky`).
2. Copy `config-template.yml` to your project directory and fill it with your data.
3. Run `flask --app "platzky.platzky:create_app(config_path='PATH_TO_YOUR_CONFIG_FILE')`

## Example

For examples check e2e tests in `tests/e2e` directory and Makefile.
