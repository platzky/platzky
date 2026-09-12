Configuration Handling
======================

Platzky uses a YAML-based configuration system built on Pydantic models. Configuration
is loaded from a YAML file and validated at startup.

Configuration Basics
--------------------

Configuration is loaded when creating the application:

.. code-block:: python

    from platzky.platzky import create_app

    app = create_app(config_path='config.yml')

You can start with the provided template:

.. code-block:: bash

    $ cp config-template.yml config.yml
    $ # Edit config.yml with your settings
    $ flask --app "platzky.platzky:create_app(config_path='config.yml')" run

Configuration Reference
-----------------------

Core Settings
~~~~~~~~~~~~~

``APP_NAME``
^^^^^^^^^^^^

:Type: ``str`` (required)

The name of your application. This is used throughout the application for display purposes.

.. code-block:: yaml

    APP_NAME: My awesome platzky application

``SECRET_KEY``
^^^^^^^^^^^^^^

:Type: ``str`` (required)

Flask's secret key used for session signing and CSRF protection.

.. warning::
    In production, this should be a random string kept secret. Never commit production
    secrets to version control.

.. code-block:: yaml

    SECRET_KEY: your-secret-key-here

See the `Flask documentation on SECRET_KEY <https://flask.palletsprojects.com/en/stable/config/#SECRET_KEY>`_
for more information.

``DEBUG``
^^^^^^^^^

:Type: ``bool``
:Default: ``False``

Enable debug mode. When enabled, the server will reload on code changes and provide
detailed error pages.

.. warning::
    Never enable debug mode in production as it can expose sensitive information.

.. code-block:: yaml

    DEBUG: true

``TESTING``
^^^^^^^^^^^

:Type: ``bool``
:Default: ``False``

Enable testing mode. This disables error catching during request handling to improve
test error reports.

.. code-block:: yaml

    TESTING: false

Database Configuration
~~~~~~~~~~~~~~~~~~~~~~

``DB``
^^^^^^

:Type: ``DBConfig`` (required)

Database configuration. Platzky supports multiple database backends.

**JSON File Database**

Store data in a local JSON file:

.. code-block:: yaml

    DB:
      TYPE: json_file
      PATH: data.json

**Google Cloud Storage Database**

Store data in Google Cloud Storage as a JSON file:

.. code-block:: yaml

    DB:
      TYPE: google_hosted_json_file
      BUCKET_NAME: my-bucket
      SOURCE_BLOB_NAME: data.json

**MongoDB Database**

Store data in MongoDB:

.. code-block:: yaml

    DB:
      TYPE: mongodb
      CONNECTION_STRING: mongodb://localhost:27017/
      DATABASE_NAME: platzky

See :doc:`database` for more details on database backends.

Localization Settings
~~~~~~~~~~~~~~~~~~~~~

``DEFAULT_LANGUAGE``
^^^^^^^^^^^^^^^^^^^^

:Type: ``str``
:Default: the only configured language, or ``"en"`` when none are configured

Language served at the root of the site. Required when more than one language is
configured, and must be one of the ``LANGUAGES`` keys.

.. code-block:: yaml

    DEFAULT_LANGUAGE: en

``LANGUAGES``
^^^^^^^^^^^^^

:Type: ``dict[str, LanguageConfig]``
:Default: ``{}``

Supported languages for the application.

Each language configuration includes:

* ``name``: Display name of the language
* ``flag``: Flag icon code (country code)
* ``country``: Country code
* ``domain`` (optional): Domain that serves this language

.. code-block:: yaml

    DEFAULT_LANGUAGE: en
    LANGUAGES:
      en:
        name: English
        flag: uk
        country: GB
        domain: example.com
      pl:
        name: polski
        flag: pl
        country: PL
      de:
        name: Deutsch
        flag: de
        country: DE
        domain: example.de

The language of a page is decided by its URL alone, so every language has exactly one
address that search engines can index:

* ``DEFAULT_LANGUAGE`` is served at the root of the site (``example.com/``).
* A language with a ``domain`` is served at the root of that domain (``example.de/``).
* Any other language is served under its code (``example.com/pl/``). This covers the
  homepage and the blog; an application can serve its own blueprint the same way with
  ``engine.localize_routes("<blueprint name>")``.

Domains must be unique, and once any other language has a ``domain`` the default language
needs one too, so pages on the other domains can link back to it. Matching ignores case, a
trailing dot, and a leading ``www.``. A ``domain`` without a port matches any port; include
a port (e.g. ``domain: example.de:5000``) to match only that port, as in local or staging
setups.

The language switcher and the ``hreflang`` tags link to each language's home page, and
``/lang/<code>`` redirects there.

``TRANSLATION_DIRECTORIES``
^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Type: ``list[str]``
:Default: ``[]``

Additional directories to search for translation files. Platzky's built-in translations
are always included.

.. code-block:: yaml

    TRANSLATION_DIRECTORIES:
      - /path/to/custom/translations
      - /another/path/translations

URL Settings
~~~~~~~~~~~~

``USE_WWW``
^^^^^^^^^^^

:Type: ``bool``
:Default: ``True``

Redirect non-www URLs to www URLs. When enabled, ``example.com`` redirects to ``www.example.com``.

.. code-block:: yaml

    USE_WWW: true

``SEO_PREFIX``
^^^^^^^^^^^^^^

:Type: ``str``
:Default: ``"/"``

URL prefix for SEO-related routes like sitemaps and robots.txt.

.. code-block:: yaml

    SEO_PREFIX: /

``BLOG_PREFIX``
^^^^^^^^^^^^^^^

:Type: ``str``
:Default: ``"/blog"``

URL prefix for blog routes. Cannot be set to ``"/"`` — the root path is reserved for
the homepage route (see `Homepage`_ below).

.. code-block:: yaml

    BLOG_PREFIX: /blog

Homepage
~~~~~~~~

The root path (``/``) renders a configurable homepage instead of a fixed template.
Platzky resolves the configured path against the application's own routes, so it can
point at a page, a post, or any other registered route.

The homepage path isn't set in ``config.yml`` — it lives in your site content,
alongside posts and pages, so it can be changed without redeploying:

* **JSON file / Google Cloud Storage**: set ``home_page_path`` in the
  ``site_content`` object of your data file.

  .. code-block:: json

      {
        "site_content": {
          "home_page_path": "/blog/page/about"
        }
      }

* **MongoDB**: set ``home_page_path`` on the site config document.

* **GraphQL (Hygraph)**: set ``homePagePath`` on the ``ApplicationSetup`` model.

Behavior:

* If no homepage path is configured, ``/`` falls back to the blog index at
  ``BLOG_PREFIX``.
* If the configured path doesn't resolve to a registered route, ``/`` renders the
  404 page.
* If the configured path resolves back to ``/`` itself, Platzky falls back to the
  blog index instead of recursing.

Feature Flags
~~~~~~~~~~~~~

``FEATURE_FLAGS``
^^^^^^^^^^^^^^^^^

:Type: ``dict[str, bool]`` (YAML) / ``FeatureFlagSet`` (internal)
:Default: ``{}``

Enable or disable specific features in your application. In YAML, supply a
mapping of flag alias to ``bool``:

.. code-block:: yaml

    FEATURE_FLAGS:
      FAKE_LOGIN: true

At runtime, flags are checked via ``engine.is_enabled(FakeLogin)``.

Built-in feature flags
""""""""""""""""""""""

.. feature-flags::

Defining custom feature flags
"""""""""""""""""""""""""""""

Downstream applications and plugins can define their own flags. Create a
``FeatureFlag`` instance with a unique ``alias``, then enable it in the
YAML config:

.. code-block:: python

    # my_app/flags.py
    from platzky.feature_flags import FeatureFlag

    DarkMode = FeatureFlag(
        alias="DARK_MODE",
        default=False,
        description="Enable dark-mode theme.",
    )

.. code-block:: yaml

    # config.yml
    FEATURE_FLAGS:
      DARK_MODE: true

Then check it at runtime:

.. code-block:: python

    from my_app.flags import DarkMode

    if app.is_enabled(DarkMode):
        ...

Resolution is dynamic: the ``FeatureFlagSet`` looks up the flag's ``alias``
in the raw config dict and falls back to its ``default``. No registration
step is required — any ``FeatureFlag`` instance can be checked against any
``FeatureFlagSet``.

A flag whose ``alias`` is absent from the YAML config resolves to its
``default`` value. This means a flag with ``default=True`` is enabled
unless the config explicitly sets it to ``false``.

Telemetry Configuration
~~~~~~~~~~~~~~~~~~~~~~~

``TELEMETRY``
^^^^^^^^^^^^^

:Type: ``TelemetryConfig``
:Default: ``{"enabled": false}``

Configure OpenTelemetry tracing to monitor application performance and identify slow code paths.

Telemetry options:

* ``enabled``: Enable/disable telemetry (default: ``false``)
* ``endpoint``: OTLP endpoint URL (optional). If not set, only console export is used
* ``console_export``: Log traces to console (default: ``false``)
* ``timeout``: Timeout in seconds for exporter (default: ``10``)
* ``deployment_environment``: Deployment environment (e.g., ``production``, ``staging``, ``dev``)
* ``service_instance_id``: Service instance ID (optional, auto-generated if not provided)

**Note:** Service version is automatically detected from package metadata. Instance ID is auto-generated from hostname + UUID if not explicitly provided.

**Console Export Only (Local Development)**

.. code-block:: yaml

    TELEMETRY:
      enabled: true
      console_export: true

**Google Cloud Trace (Google App Engine)**

.. code-block:: yaml

    TELEMETRY:
      enabled: true
      endpoint: https://telemetry.googleapis.com

**OTLP Exporter (Jaeger, Tempo, etc.)**

.. code-block:: yaml

    TELEMETRY:
      enabled: true
      endpoint: http://localhost:4317

**Multiple Exporters**

Export to both a backend and console:

.. code-block:: yaml

    TELEMETRY:
      enabled: true
      endpoint: http://localhost:4317
      console_export: true

**Required Dependencies**

Install telemetry dependencies:

.. code-block:: bash

    # Install platzky with telemetry support
    $ poetry install -E telemetry

Or if installing from PyPI:

.. code-block:: bash

    $ pip install platzky[telemetry]

Complete Example
----------------

Here's a complete configuration example for a production application:

.. code-block:: yaml

    # Core settings
    APP_NAME: My Production Blog
    SECRET_KEY: change-this-to-a-random-secret-in-production

    # Enable features
    FEATURE_FLAGS:
      comments: true
      analytics: true

    # Database
    DB:
      TYPE: mongodb
      CONNECTION_STRING: mongodb://db-server:27017/
      DATABASE_NAME: myblog

    # Multi-language support
    DEFAULT_LANGUAGE: en
    LANGUAGES:
      en:
        name: English
        flag: uk
        country: GB
        domain: myblog.com
      de:
        name: Deutsch
        flag: de
        country: DE
        domain: myblog.de  # German is served at myblog.de

    # URLs
    USE_WWW: true
    BLOG_PREFIX: /blog

Environment-Specific Configuration
-----------------------------------

For managing different configurations across environments (development, staging, production),
you can:

**Use different config files:**

.. code-block:: bash

    $ flask --app "platzky.platzky:create_app(config_path='config-prod.yml')" run

**Use environment variables in your config:**

.. code-block:: yaml

    SECRET_KEY: ${SECRET_KEY}
    DB:
      CONNECTION_STRING: ${DATABASE_URL}

**Load config from environment-specific paths:**

.. code-block:: python

    import os
    env = os.getenv('ENVIRONMENT', 'development')
    app = create_app(config_path=f'config-{env}.yml')

Configuration Validation
------------------------

Platzky validates configuration at startup using Pydantic. If your configuration is
invalid, you'll receive a clear error message indicating what's wrong:

.. code-block:: text

    Config file not found: config.yml

or

.. code-block:: text

    ValidationError: 1 validation error for Config
    SECRET_KEY
      field required (type=value_error.missing)

This ensures you catch configuration errors early before deployment.
