Plugins
=======

.. versionadded:: 1.2.0

Platzky includes an extensible plugin system that allows you to add custom functionality
to your application. Plugins can add notifiers, login methods, CMS modules, health checks,
dynamic content, and more.

Overview
--------

Plugins are external Python packages that follow the naming convention ``platzky_<name>``.
For example, a plugin called ``analytics`` would be packaged as ``platzky_analytics``.

There are two plugin styles:

* **Class-based** (preferred): Extend ``PluginBase`` and implement the ``process`` method
* **Legacy** (deprecated): A module with a ``process(app, config)`` function

Creating a Plugin (Class-based)
-------------------------------

A class-based plugin consists of three parts:

1. A Pydantic config model extending ``PluginBaseConfig``
2. A plugin class extending ``PluginBase``
3. A module-level ``Plugin`` attribute pointing to your class

Here is a minimal example:

.. code-block:: python

    from platzky.engine import Engine
    from platzky.plugin.plugin import PluginBase, PluginBaseConfig


    class MyPluginConfig(PluginBaseConfig):
        """Configuration for the plugin."""

        api_key: str
        enabled: bool = True


    class MyPlugin(PluginBase[MyPluginConfig]):
        """A plugin that adds custom functionality."""

        @classmethod
        def get_config_model(cls) -> type[MyPluginConfig]:
            return MyPluginConfig

        def process(self, app: Engine) -> Engine:
            if self.config.enabled:
                app.add_health_check("my_plugin", lambda: None)
            return app


    # Required: module-level attribute for plugin discovery
    Plugin = MyPlugin

**Key points:**

* Override ``get_config_model()`` to return your config class so Platzky can validate
  the plugin configuration automatically.
* The ``process`` method receives the Platzky ``Engine`` (a Flask subclass) and must
  return it after applying modifications.
* The module must expose a ``Plugin`` attribute at the top level.

**Optional overrides:**

* Add a ``config: MyPluginConfig`` type hint to the class body for better type checking.
* Override ``__init__`` if you need custom initialization beyond config validation.

Plugin Configuration
--------------------

Plugins are configured through the database. The ``get_plugins_data()`` method on the
database returns a list of plugin entries, each with the following structure:

.. code-block:: python

    {
        "name": "platzky_analytics",
        "config": {
            "api_key": "abc123",
            "enabled": True
        }
    }

The ``name`` field must match the installed Python package name (``platzky_<name>``).
The ``config`` dictionary is passed to the plugin's constructor and validated against
the plugin's config model.

Engine Extension Points
-----------------------

The ``Engine`` class provides several methods that plugins can use to extend the
application:

``add_notifier(notifier)``
~~~~~~~~~~~~~~~~~~~~~~~~~~

Register a notifier that receives message strings. Notifiers are called when the
application triggers a notification via ``engine.notify(message)``.

.. code-block:: python

    def process(self, app: Engine) -> Engine:
        app.add_notifier(lambda msg: print(f"Notification: {msg}"))
        return app

``add_notifier_with_attachments(notifier)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Register a notifier that supports attachments. The notifier receives a message string
and an optional list of attachments.

``add_cms_module(module)``
~~~~~~~~~~~~~~~~~~~~~~~~~~

Add a CMS module to the application. CMS modules appear in the admin panel.

.. code-block:: python

    from platzky.models import CmsModule

    def process(self, app: Engine) -> Engine:
        module = CmsModule(name="Analytics", url="/analytics")
        app.add_cms_module(module)
        return app

``add_login_method(login_method)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Register an additional login method for the admin panel.

``add_dynamic_body(body)``
~~~~~~~~~~~~~~~~~~~~~~~~~~

Append HTML content to the page body. Useful for injecting scripts or widgets.

.. code-block:: python

    def process(self, app: Engine) -> Engine:
        app.add_dynamic_body('<script src="/analytics.js"></script>')
        return app

``add_dynamic_head(head)``
~~~~~~~~~~~~~~~~~~~~~~~~~~

Append HTML content to the page head. Useful for injecting stylesheets or meta tags.

``add_health_check(name, check_function)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Register a health check that is included in the ``/health/readiness`` endpoint.
The check function should raise an exception if the check fails.

.. code-block:: python

    import requests

    def process(self, app: Engine) -> Engine:
        def check():
            # Raise an exception if unhealthy
            response = requests.get("https://api.example.com/health")
            response.raise_for_status()

        app.add_health_check("external_api", check)
        return app

``is_enabled(flag)``
~~~~~~~~~~~~~~~~~~~~

Check whether a feature flag is enabled. Plugins can use this to conditionally
activate functionality.

.. code-block:: python

    from platzky.feature_flags import FeatureFlag

    def process(self, app: Engine) -> Engine:
        if app.is_enabled(FeatureFlag.SOME_FLAG):
            # Enable feature
            pass
        return app

Translation Support
-------------------

Plugins can provide their own translation files. To add translations:

1. Create a ``locale`` directory inside your plugin package:

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

2. The ``get_locale_dir()`` method on ``PluginBase`` automatically discovers the
   ``locale`` directory relative to your plugin module. Platzky registers it with
   Flask-Babel during plugin loading.

Legacy Plugins
--------------

.. deprecated:: 1.2.0
    Legacy plugins are deprecated and will be removed in 2.0.0.
    Use the class-based style instead.

Legacy plugins are modules with a ``process`` function:

.. code-block:: python

    def process(app, config):
        # Modify the app
        return app

This style does not support configuration validation or translation discovery.
Migrate to the class-based style by extending ``PluginBase``.
