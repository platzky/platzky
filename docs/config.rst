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

``LANGUAGES``
^^^^^^^^^^^^^

:Type: ``dict[str, LanguageConfig]``
:Default: ``{}``

Supported languages for the application. The first language is used as the default.

Each language configuration includes:

* ``name``: Display name of the language
* ``flag``: Flag icon code (country code)
* ``country``: Country code
* ``domain`` (optional): Specific domain for this language

.. code-block:: yaml

    LANGUAGES:
      en:
        name: English
        flag: uk
        country: GB
      pl:
        name: polski
        flag: pl
        country: PL
      de:
        name: Deutsch
        flag: de
        country: DE
        domain: example.de  # Optional: language-specific domain

``DOMAIN_TO_LANG``
^^^^^^^^^^^^^^^^^^

:Type: ``dict[str, str]``
:Default: ``{}``

Map domains to specific languages. Useful for serving different languages on different domains.

.. code-block:: yaml

    DOMAIN_TO_LANG:
      example.com: en
      example.de: de
      example.pl: pl

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
:Default: ``"/"``

URL prefix for blog routes.

.. code-block:: yaml

    BLOG_PREFIX: /blog

Feature Flags
~~~~~~~~~~~~~

``FEATURE_FLAGS``
^^^^^^^^^^^^^^^^^

:Type: ``dict[str, bool]``
:Default: ``{}``

Enable or disable specific features in your application.

Available feature flags:

**FAKE_LOGIN**

Enable fake/test login for the admin panel. Useful for development and testing environments.

.. warning::
    Never enable FAKE_LOGIN in production as it bypasses authentication.

.. code-block:: yaml

    FEATURE_FLAGS:
      FAKE_LOGIN: true

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

**Console Export Only (Local Development)**

.. code-block:: yaml

    TELEMETRY:
      enabled: true
      console_export: true

**Google Cloud Trace (Google App Engine)**

.. code-block:: yaml

    TELEMETRY:
      enabled: true
      endpoint: https://cloudtrace.googleapis.com/v2/projects/YOUR-PROJECT-ID/traces

Or auto-detect project from environment:

.. code-block:: python

    import os
    endpoint = f"https://cloudtrace.googleapis.com/v2/projects/{os.getenv('GOOGLE_CLOUD_PROJECT')}/traces"

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

    # For console or OTLP exporters
    $ poetry add opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-flask opentelemetry-exporter-otlp-proto-grpc

    # For Google Cloud Trace (alternative to OTLP)
    $ poetry add opentelemetry-instrumentation-flask opentelemetry-exporter-gcp-trace

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
    LANGUAGES:
      en:
        name: English
        flag: uk
        country: GB
      de:
        name: Deutsch
        flag: de
        country: DE

    DOMAIN_TO_LANG:
      myblog.com: en
      myblog.de: de

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
