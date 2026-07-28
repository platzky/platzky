Database Backends
=================

Platzky supports multiple database backends for storing your application data. You can
choose the backend that best fits your deployment environment and requirements.

Configuring the Database
------------------------

The database backend is configured in your ``config.yml`` file using the ``DB`` key:

.. code-block:: yaml

    DB:
      TYPE: backend_type
      # backend-specific configuration

Available Backends
------------------

JSON File
~~~~~~~~~

A simple file-based backend that stores data in a JSON file on the local filesystem.

**Use case:** Development, testing, or small single-server deployments.

**Configuration:**

.. code-block:: yaml

    DB:
      TYPE: json_file
      PATH: data.json

**Options:**

* ``TYPE``: Must be ``json_file``
* ``PATH``: Path to the JSON file (relative or absolute)

**Advantages:**

* Simple setup, no external dependencies
* Easy to inspect and backup (just a JSON file)
* Good for development and testing

**Limitations:**

* Not suitable for high-traffic applications
* No concurrent write support
* Single point of failure

Google Cloud Storage
~~~~~~~~~~~~~~~~~~~~

Stores data as a JSON file in Google Cloud Storage bucket.

**Use case:** Google App Engine or other Google Cloud deployments where you want
simple storage without running a database server.

**Configuration:**

.. code-block:: yaml

    DB:
      TYPE: google_json
      BUCKET_NAME: my-bucket
      SOURCE_BLOB_NAME: data.json

**Options:**

* ``TYPE``: Must be ``google_json``
* ``BUCKET_NAME``: Name of the GCS bucket
* ``SOURCE_BLOB_NAME``: Name of the JSON file in the bucket

**Prerequisites:**

* Application must have Google Cloud credentials configured
* Service account must have read/write permissions on the bucket

**Advantages:**

* Automatic backups and versioning (when enabled on bucket)
* No database server to manage
* Integrates well with Google Cloud Platform

**Limitations:**

* Higher latency than local storage
* Costs associated with GCS operations
* Not suitable for high-frequency writes
* Read-only from Platzky's perspective: writes raise an error rather than
  being persisted back to the bucket

GitHub JSON
~~~~~~~~~~~

Stores data as a JSON file in a GitHub repository, fetched via the GitHub API.

**Use case:** Content you want version-controlled and human-reviewable through
normal GitHub workflows (PRs, history, diffs), without running a database server.

**Configuration:**

.. code-block:: yaml

    DB:
      TYPE: github_json
      REPO_NAME: username/repository
      GITHUB_TOKEN: your_github_token
      PATH_TO_FILE: data.json
      BRANCH_NAME: main

**Options:**

* ``TYPE``: Must be ``github_json``
* ``REPO_NAME``: Repository in ``owner/repo`` form
* ``GITHUB_TOKEN``: GitHub token with read access to the repository (write
  access if you need commits back)
* ``PATH_TO_FILE``: Path to the JSON file within the repository
* ``BRANCH_NAME``: Branch to read from (defaults to ``main``)

**Prerequisites:**

* A GitHub token with access to the target repository

**Advantages:**

* Full version history and diffs for free, via GitHub
* Content changes can go through normal PR review
* No database server to manage

**Limitations:**

* Higher latency than local storage (network call to GitHub's API)
* Subject to GitHub API rate limits
* Read-only from Platzky's perspective: writes raise an error rather than
  being persisted back to the repository
* Not suitable for high-frequency writes

GraphQL (Headless CMS)
~~~~~~~~~~~~~~~~~~~~~~

Reads content from a GraphQL API, such as a Hygraph (formerly GraphCMS) endpoint.

**Use case:** Content is managed in an external headless CMS rather than by
Platzky itself.

**Configuration:**

.. code-block:: yaml

    DB:
      TYPE: graph_ql
      CMS_ENDPOINT: https://your-graphql-endpoint.com/api
      CMS_TOKEN: your_graphql_token

**Options:**

* ``TYPE``: Must be ``graph_ql``
* ``CMS_ENDPOINT``: URL of the GraphQL API
* ``CMS_TOKEN``: Access token for the GraphQL API

**Advantages:**

* Content management handled by a dedicated CMS
* No database server to manage on Platzky's side

**Limitations:**

* Read-only: this backend does not support writes from Platzky
* Branding/site-settings fields are not sourced from the CMS and are
  currently hardcoded defaults
* Requires an external CMS subscription/deployment

MongoDB
~~~~~~~

A production-ready NoSQL database backend.

**Use case:** Production deployments requiring scalability, concurrent access, and
advanced database features.

**Configuration:**

.. code-block:: yaml

    DB:
      TYPE: mongodb
      CONNECTION_STRING: mongodb://localhost:27017/
      DATABASE_NAME: platzky

**Options:**

* ``TYPE``: Must be ``mongodb``
* ``CONNECTION_STRING``: MongoDB connection string
* ``DATABASE_NAME``: Name of the database to use

**Connection String Examples:**

Local MongoDB:

.. code-block:: yaml

    CONNECTION_STRING: mongodb://localhost:27017/

MongoDB Atlas:

.. code-block:: yaml

    CONNECTION_STRING: mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority

With authentication:

.. code-block:: yaml

    CONNECTION_STRING: mongodb://username:password@localhost:27017/

**Advantages:**

* Production-ready with high availability options
* Supports concurrent reads and writes
* Automatic indexing and query optimization
* Rich query capabilities
* Horizontal scaling with sharding

**Prerequisites:**

* MongoDB server (local, Docker, or managed service like Atlas)
* ``pymongo`` package (included with Platzky)

Choosing a Backend
------------------

Development
~~~~~~~~~~~

For local development, use the JSON file backend:

.. code-block:: yaml

    DB:
      TYPE: json_file
      PATH: data-dev.json

This requires no additional setup and is easy to reset.

Google App Engine
~~~~~~~~~~~~~~~~~

For Google App Engine, you have two options:

1. **Google Cloud Storage** (simpler, good for low-traffic apps):

   .. code-block:: yaml

       DB:
         TYPE: google_json
         BUCKET_NAME: my-app-data
         SOURCE_BLOB_NAME: data.json

2. **MongoDB Atlas** (better for production):

   .. code-block:: yaml

       DB:
         TYPE: mongodb
         CONNECTION_STRING: mongodb+srv://user:pass@cluster.mongodb.net/
         DATABASE_NAME: myapp

Kubernetes
~~~~~~~~~~

For Kubernetes deployments, use MongoDB:

.. code-block:: yaml

    DB:
      TYPE: mongodb
      CONNECTION_STRING: mongodb://mongodb-service:27017/
      DATABASE_NAME: platzky

Deploy MongoDB in your cluster or use a managed service.

Other Cloud Platforms
~~~~~~~~~~~~~~~~~~~~~

For AWS, Azure, or other platforms:

* Use MongoDB (self-hosted or managed like Atlas)
* Or use the JSON file backend with persistent volumes (for small applications)

Database Migrations
-------------------

Currently, Platzky does not include automatic migration tools when switching between
database backends. If you need to migrate:

1. Export data from your current backend
2. Update configuration to new backend
3. Import data to new backend

This is an area of active development.

Health Checks
-------------

All database backends implement health checks that are automatically included in the
``/health/readiness`` endpoint. This allows your orchestration platform (Kubernetes,
App Engine, etc.) to verify database connectivity before routing traffic.

Further Reading
---------------

* `MongoDB Documentation <https://docs.mongodb.com/>`_
* `Google Cloud Storage Documentation <https://cloud.google.com/storage/docs>`_
* `MongoDB Atlas <https://www.mongodb.com/cloud/atlas>`_
