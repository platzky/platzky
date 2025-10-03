Quickstart
==========

Eager to get started? This page gives a good introduction to Platzky.

A Minimal Application
---------------------

1. Install Platzky:

.. code-block:: bash

    $ pip install platzky

2. Create a configuration file ``config.yml``:

.. code-block:: yaml

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

3. Run the application:

.. code-block:: bash

    $ flask --app "platzky.platzky:create_app(config_path='config.yml')" run

4. Open http://127.0.0.1:5000 in your browser.

Configuration
-------------

Platzky uses a YAML configuration file. Start with the provided template:

.. code-block:: bash

    $ cp config-template.yml config.yml
    $ # Edit config.yml with your settings

See :doc:`config` for detailed configuration options.

What to Do Next
---------------

* Read about :doc:`config` to understand all available options
* Learn about different :doc:`database` backends
* Set up :doc:`telemetry` to monitor performance
* Check the :doc:`api` reference for detailed information
