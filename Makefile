lint:
	poetry run black .
	poetry run ruff check --fix .

dev: lint
	poetry run pyright .

lint-check:
	poetry run black --check .
	poetry run ruff check .
	poetry run pyright .

unit-tests:
	poetry run python -m pytest -v

unit-tests-no-coverage:
	poetry run python -m pytest -m "skip_coverage"

e2e-tests:
	cd tests/e2e_tests && node_modules/cypress/bin/cypress run --browser chromium

coverage:
	poetry run coverage run --branch --source=platzky -m pytest -m "not skip_coverage"
	poetry run coverage lcov

html-cov: coverage
	poetry run coverage html

run-e2e-instance:
	poetry run flask --app "platzky.platzky:create_app(config_path='tests/e2e_tests/e2e_test_config.yml')" run --debug

extract-translations:
	poetry run pybabel extract ./platzky -o extracted.pot -F ./babel.cfg --project=platzky
	poetry run pybabel update -i extracted.pot -d platzky/locale --ignore-pot-creation-date --ignore-obsolete

build:
	poetry run pybabel compile -d platzky/locale
	poetry build
