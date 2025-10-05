Installation
============

Python Version
--------------

Platzky requires Python 3.10 or higher.

Installing Platzky
------------------

Install Platzky using pip:

.. code-block:: bash

    $ pip install platzky

Or with Poetry:

.. code-block:: bash

    $ poetry add platzky

Optional Dependencies
---------------------

Platzky has optional dependencies that can be installed separately:

Telemetry Support
~~~~~~~~~~~~~~~~~

For OpenTelemetry tracing support:

.. code-block:: bash

    $ pip install platzky[telemetry]

Or with Poetry:

.. code-block:: bash

    $ poetry add platzky -E telemetry

This installs:

* opentelemetry-api
* opentelemetry-sdk
* opentelemetry-instrumentation-flask
* opentelemetry-instrumentation-pymongo
* opentelemetry-instrumentation-requests
* opentelemetry-exporter-otlp

See :doc:`telemetry` for more information on configuring telemetry.

Verify Installation
-------------------

To verify that Platzky is installed correctly:

.. code-block:: python

    >>> import platzky
    >>> print(platzky.__version__)
    |version|
