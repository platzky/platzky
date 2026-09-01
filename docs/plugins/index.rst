Plugins
=======

.. versionadded:: 1.2.0

Platzky includes an extensible plugin system that allows you to add custom functionality
to your application. Plugins can add notifiers, content transformers, shortcodes, login
methods, CMS modules, health checks, dynamic content, and more.

Overview
--------

Plugins are ordinary Python packages installed into the same environment as Platzky.
They advertise themselves via the ``platzky.plugins`` entry-point group and are
discovered automatically at startup.

Since 1.5.0, plugins are built around *plugin base classes*. Pick the one that
matches what your plugin does:

.. plugin-bases::

Quick Start with Cookiecutter
-----------------------------

The fastest way to create a new plugin is using the official
`cookiecutter template <https://github.com/platzky/plugin-cookiecutter>`_:

.. code-block:: bash

    pip install cookiecutter
    cookiecutter gh:platzky/plugin-cookiecutter

You will be prompted for:

* ``plugin_name`` — snake_case name for your plugin (e.g. ``analytics``)
* ``plugin_class_name`` — PascalCase class name
* ``description`` — short description of the plugin
* ``author`` — author name for license and package metadata

The generated project includes a ``PluginBase`` subclass as a starting point,
``pyproject.toml`` with the ``platzky.plugins`` entry point already wired up,
and a Makefile with ``lint``, ``dev``, ``unit-tests``, ``coverage``, and ``build``
targets.

After generation:

.. code-block:: bash

    cd platzky-<your_plugin_name>
    poetry install
    make dev          # lint + type check
    make unit-tests   # run tests

Capabilities
------------

What a plugin can do is decided by which base classes it subclasses. One plugin may
subclass several.

.. toctree::
   :maxdepth: 2

   content-transformers
   shortcodes
   capabilities

The rest of this page is what every plugin needs regardless of capability: how to
package it, how an operator configures it, and how it is listed and translated.

Accessing the Engine from Request Handlers
-------------------------------------------

Flask's own ``current_app`` proxy is typed as plain ``Flask``, so it doesn't expose
Engine-specific methods like ``notify`` or ``is_enabled`` to a type checker. If a
plugin registers its own routes and needs the Engine from inside a view function
(where ``app`` isn't otherwise in scope), use :func:`platzky.current_engine` instead:

.. code-block:: python

    from platzky import current_engine

    @blueprint.route("/webhook", methods=["POST"])
    def handle_webhook():
        current_engine().notify("Webhook received", topic="general")
        return "", 204

Packaging a Plugin
------------------

Plugins are discovered via the ``platzky.plugins`` entry-point group. Declare your
plugin class in ``pyproject.toml``. With Poetry:

.. code-block:: toml

    [tool.poetry.plugins."platzky.plugins"]
    my_plugin = "platzky_my_plugin:MyPlugin"

Or, using the standard PEP 621 table (setuptools, hatch, and other PEP 621 build
backends):

.. code-block:: toml

    [project.entry-points."platzky.plugins"]
    my_plugin = "platzky_my_plugin:MyPlugin"

The key (``my_plugin``) is the name used in the database configuration. The two are one
name, not two: the loader looks a config key up among the installed entry-point names, so
a plugin whose entry point and config key differ never loads at all. The engine stamps it
onto the instance as :attr:`~platzky.plugin.plugin.PluginBase.name` when the plugin is
registered — which is why it is empty while the plugin's own ``__init__`` runs — and
``get_info()`` reports it, falling back to the class name for a plugin never registered
with an engine.

.. _plugin-configuration:

Plugin Configuration
--------------------

After the package is installed, activate the plugin by adding it to the ``plugins``
dict in your database. The key is the entry-point name declared in ``pyproject.toml``:

.. code-block:: json

    {
        "plugins": {
            "my_plugin": {
                "is_active": true,
                "config": { "api_key": "abc123" }
            }
        }
    }

The ``config`` object is passed as a ``dict[str, Any]`` to the plugin's ``__init__``.
Plugins with ``is_active`` absent or ``false`` are skipped at startup.

For notifier plugins you can restrict which topics the plugin receives:

.. code-block:: json

    {
        "plugins": {
            "slack_notifier": {
                "is_active": true,
                "config": { "webhook_url": "https://hooks.slack.com/…" },
                "allowed_topics": ["security", "general"]
            }
        }
    }

For content transformer plugins, ``allowed_content_types`` names the content types the
plugin may act on — the operator's half of the two-key contract in
:ref:`declaring-scope`. Omitting it grants nothing, and naming a type the plugin does not
offer grants nothing either. Include an application's own type (here ``"field"``) to let
the plugin's shortcodes render stored values of that kind as well as prose:

.. code-block:: json

    {
        "plugins": {
            "alert_plugin": {
                "is_active": true,
                "config": {},
                "allowed_content_types": ["post", "page", "field"]
            }
        }
    }

For page decorator plugins you can restrict which page sections the plugin may
inject into:

.. code-block:: json

    {
        "plugins": {
            "analytics_plugin": {
                "is_active": true,
                "config": { "tracking_id": "UA-XXXXX-Y" },
                "allowed_page_sections": ["head"]
            }
        }
    }

Admin Help Page
---------------

Loaded plugins and their shortcodes are listed on the admin *Help* page
(``/admin/help``). A plugin is listed under its own ``name`` — the entry-point name it is
installed and configured under — so an operator reading the page can find it in their
config. The description comes from the class docstring; override ``get_info()`` to write
one by hand:

.. code-block:: python

    from platzky.plugin.plugin import PluginBase, PluginInfo

    class MyPlugin(PluginBase):
        def get_info(self) -> PluginInfo:
            return PluginInfo(name=self.name, description="Does something useful.")

Translation Support
-------------------

Plugins can provide their own translation files. Place them under a ``locale/``
directory inside your plugin package:

.. code-block:: text

    platzky_myplugin/
        __init__.py
        plugin.py
        locale/
            en/
                LC_MESSAGES/
                    messages.po
                    messages.mo
            pl/
                LC_MESSAGES/
                    messages.po
                    messages.mo

``PluginBase.get_locale_dir()`` discovers the directory automatically. Platzky
registers it with Flask-Babel during plugin loading.

