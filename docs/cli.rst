Command Line Interface
======================

Installing Platzky provides the ``platzky`` command. Run ``platzky --help``, or
``platzky <command> --help``, for the options of each command.

``platzky init``
----------------

Set up a new site in the current directory, or in ``--path``:

.. code-block:: bash

    $ platzky init

It writes two files and refuses to overwrite either if it already exists:

* ``config.yml`` — a placeholder ``APP_NAME`` to replace with your own, a freshly generated
  ``SECRET_KEY``, English as the only language, the ``json_file`` backend pointing at
  ``data.json``, and every built-in feature flag listed commented out at its default
* ``data.json`` — one sample post, an About page and a menu linking to both, so the site
  serves pages straight away

Edit both to make the site your own: see :doc:`config` for the configuration options and
:doc:`database` for the content structure.

``platzky run``
---------------

Run the development server:

.. code-block:: bash

    $ platzky run --config config.yml

This is development mode: the server reloads on code changes, shows the interactive debugger
on errors, logs at ``DEBUG``, and allows shortcuts that are unsafe in production, such as the
``FAKE_LOGIN`` feature flag. There is no setting for it — running this command *is* the
switch, and an application served by a production server is never in development mode.

.. warning::
    This is Flask's development server. For production, serve the application with a WSGI
    server such as gunicorn.

Running in Production
---------------------

A Platzky application is an ordinary WSGI application, so serve it with a production server:

.. code-block:: bash

    $ gunicorn "platzky.platzky:create_app(config_path='config.yml')"

Started this way the application is not in development mode: no reloader, no interactive
debugger, and ``FAKE_LOGIN`` is refused. Set ``LOG_LEVEL`` if you need verbose logs there.

Outside development mode the application also assumes it is served over HTTPS:

* It trusts ``X-Forwarded-Proto`` from one proxy in front of it, as set by Google App Engine,
  Cloud Run, or a TLS-terminating reverse proxy such as nginx or Caddy. That proxy must
  overwrite the header rather than pass on a client-supplied one. When proxies are chained,
  for example a load balancer in front of nginx, the inner one must forward the outer one's
  ``X-Forwarded-Proto`` instead of its own scheme. The client address is not taken from
  ``X-Forwarded-For``.
* The session cookie is marked ``Secure``.
* HTTPS responses carry ``Strict-Transport-Security: max-age=31536000``, so browsers use only
  HTTPS for that host for a year.

.. warning::
    Serving a production application over plain HTTP is not supported. Browsers drop the
    ``Secure`` session cookie there, so admin login, CSRF-protected forms such as comments, and
    the language choice all stop working. Chrome and Firefox treat ``http://localhost`` as
    secure, so a production build tried locally still works there.
