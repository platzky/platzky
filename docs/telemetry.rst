Telemetry
=========

.. versionadded:: 0.5.0

Platzky includes OpenTelemetry integration for distributed tracing and performance
monitoring. This helps identify bottlenecks in your application, whether running on
Google App Engine, Kubernetes, or any other platform.

Why Telemetry?
--------------

Telemetry gives you visibility into:

* Request latency and throughput
* Database query performance
* External API call durations
* Bottlenecks in your application code

This is especially valuable when running in production environments where traditional
debugging isn't available.

Installation
------------

Telemetry support requires optional dependencies:

.. code-block:: bash

    $ pip install platzky[telemetry]

Or with Poetry:

.. code-block:: bash

    $ poetry install -E telemetry

This installs:

* ``opentelemetry-api`` - Core OpenTelemetry API
* ``opentelemetry-sdk`` - OpenTelemetry SDK
* ``opentelemetry-instrumentation-flask`` - Automatic Flask instrumentation
* ``opentelemetry-instrumentation-pymongo`` - Automatic MongoDB instrumentation
* ``opentelemetry-instrumentation-requests`` - Automatic HTTP client instrumentation
* ``opentelemetry-exporter-otlp`` - OTLP exporter for sending traces

Configuration
-------------

Enable telemetry in your ``config.yml``:

.. code-block:: yaml

    TELEMETRY:
      enabled: true
      otlp_endpoint: http://localhost:4317

Configuration Options
~~~~~~~~~~~~~~~~~~~~~

``enabled``
^^^^^^^^^^^

:Type: ``bool``
:Default: ``False``

Enable or disable telemetry collection.

``otlp_endpoint``
^^^^^^^^^^^^^^^^^

:Type: ``str``
:Default: ``"http://localhost:4317"``

OTLP gRPC endpoint for exporting traces. This endpoint should point to your
OpenTelemetry collector or observability backend.

What Gets Traced?
-----------------

When telemetry is enabled, Platzky automatically instruments:

Flask Requests
~~~~~~~~~~~~~~

Every HTTP request is traced with:

* Request method and path
* Response status code
* Request duration
* Query parameters and headers (configurable)

MongoDB Queries
~~~~~~~~~~~~~~~

If you're using MongoDB, all database operations are traced:

* Query operations (find, insert, update, delete)
* Database and collection names
* Query duration

HTTP Requests
~~~~~~~~~~~~~

Outgoing HTTP requests made with the ``requests`` library are traced:

* URL and method
* Response status code
* Request duration

Deployment Examples
-------------------

Local Development with Jaeger
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run Jaeger locally with Docker:

.. code-block:: bash

    $ docker run -d --name jaeger \
      -p 4317:4317 \
      -p 16686:16686 \
      jaegertracing/all-in-one:latest

Configure Platzky:

.. code-block:: yaml

    TELEMETRY:
      enabled: true
      otlp_endpoint: http://localhost:4317

View traces at http://localhost:16686

Kubernetes with Grafana Tempo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Deploy Grafana Tempo in your cluster, then configure:

.. code-block:: yaml

    TELEMETRY:
      enabled: true
      otlp_endpoint: http://tempo-distributor.monitoring.svc.cluster.local:4317

Google App Engine
~~~~~~~~~~~~~~~~~

Use Google Cloud's OpenTelemetry collector:

1. Deploy the OpenTelemetry Collector to your GCP project
2. Configure Platzky:

.. code-block:: yaml

    TELEMETRY:
      enabled: true
      otlp_endpoint: http://opentelemetry-collector:4317

View traces in Google Cloud Trace console.

AWS with X-Ray
~~~~~~~~~~~~~~

Use AWS Distro for OpenTelemetry:

.. code-block:: yaml

    TELEMETRY:
      enabled: true
      otlp_endpoint: http://localhost:4317  # ADOT collector

View traces in AWS X-Ray console.

Analyzing Traces
----------------

Once telemetry is collecting data, you can:

Identify Slow Requests
~~~~~~~~~~~~~~~~~~~~~~

Look for HTTP request spans with high duration. The trace will show you:

* Which route is slow
* What's causing the slowness (database query, external API, etc.)

Optimize Database Queries
~~~~~~~~~~~~~~~~~~~~~~~~~~

MongoDB query spans show:

* Query duration
* Which queries are most frequent
* N+1 query patterns

Find External API Bottlenecks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

HTTP client spans reveal:

* Which external APIs are slow
* Timeout issues
* Rate limiting problems

Best Practices
--------------

Development vs Production
~~~~~~~~~~~~~~~~~~~~~~~~~

Consider disabling telemetry in development to reduce noise:

.. code-block:: yaml

    # config-dev.yml
    TELEMETRY:
      enabled: false

    # config-prod.yml
    TELEMETRY:
      enabled: true
      otlp_endpoint: http://tempo-collector:4317

Sampling
~~~~~~~~

In high-traffic applications, consider configuring sampling at the collector level
to reduce overhead and costs. Most observability platforms support trace sampling.

Privacy Considerations
~~~~~~~~~~~~~~~~~~~~~~

Be aware that traces may contain:

* Request URLs (which might include sensitive parameters)
* Database query details
* Response data

Configure your instrumentation appropriately for your privacy requirements.

Troubleshooting
---------------

No Traces Appearing
~~~~~~~~~~~~~~~~~~~

1. Verify telemetry dependencies are installed:

   .. code-block:: bash

       $ pip list | grep opentelemetry

2. Check the OTLP endpoint is reachable:

   .. code-block:: bash

       $ telnet tempo-collector 4317

3. Look for OpenTelemetry warnings in application logs

High Overhead
~~~~~~~~~~~~~

If telemetry is causing performance issues:

1. Verify you're using an async exporter (OTLP uses async by default)
2. Configure sampling at the collector level
3. Check network latency to your OTLP endpoint

Further Reading
---------------

* `OpenTelemetry Documentation <https://opentelemetry.io/docs/>`_
* `OTLP Specification <https://opentelemetry.io/docs/specs/otlp/>`_
* `Jaeger Documentation <https://www.jaegertracing.io/docs/>`_
* `Grafana Tempo Documentation <https://grafana.com/docs/tempo/latest/>`_
