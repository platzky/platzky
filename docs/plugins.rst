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

Notifier Plugins
----------------

.. versionadded:: 1.5.0

The three built-in topics are ``"security"``, ``"content"``, and ``"general"``.

.. code-block:: python

    from typing import Any
    from platzky import Notification, NotifierPluginBase, NotificationTopic

    class SlackNotifier(NotifierPluginBase):
        """Send notifications to a Slack channel."""

        accepted_topics: frozenset[NotificationTopic] = frozenset({"general", "security"})

        def __init__(self, config: dict[str, Any]) -> None:
            super().__init__(config)
            self._webhook = config.get("webhook_url", "")

        def notify(self, notification: Notification) -> None:
            # post to self._webhook …
            pass

Notifications carry ``message``, ``topic``, ``attachments`` (a ``frozenset`` of
:class:`~platzky.attachment.Attachment`), and ``receivers`` (a
``frozenset[str]``; empty means nobody specific — send to the channel). Access
whichever fields your plugin needs.

Content Transformer Plugins
---------------------------

.. versionadded:: 1.5.0

Available content types are defined in :data:`platzky.content_types.ContentType`.
See :ref:`field-rendering` below for the meaning of ``"field"``.

.. code-block:: python

    from typing import Any
    from platzky import ContentTransformerPluginBase, ContentType

    class EmojiPlugin(ContentTransformerPluginBase):
        """Replace :smile: tokens with emoji in posts and pages."""

        accepted_content_types: frozenset[ContentType] = frozenset({"post", "page"})

        def transform_text(self, text: str) -> str:
            return text.replace(":smile:", "😊")

Override ``transform_text`` to apply plain-text transformations. The framework
guarantees that shortcode tags are excluded from the text passed here and
re-inserted after transformation. ``transform_content`` is ``@final`` and must
not be overridden.

Shortcodes
~~~~~~~~~~

Content transformer plugins can also register *shortcodes* — bracket-style tags
that content authors embed in posts and pages.

**Syntax**

.. code-block:: text

    [tagname attr="val"]              # void (no inner content)
    [tagname attr="val"]content[/tagname]  # block

Declare ``shortcodes`` as a class variable:

.. code-block:: python

    from typing import ClassVar
    from markupsafe import Markup, escape
    from platzky import ContentTransformerPluginBase, ContentType
    from platzky.shortcodes import Shortcode, ShortcodeAttrs, ShortcodeAttr

    class _AlertShortcode(Shortcode):
        name = "alert"
        description = "Render content inside a Bootstrap alert box."
        attributes = ShortcodeAttrs([
            ShortcodeAttr("type", "Alert type: info, warning, danger", required=False),
        ])
        example = '[alert type="warning"]Watch out![/alert]'

        def render(self, attrs: ShortcodeAttrs, content: str) -> str:
            kind = attrs.type or "info"
            return str(Markup('<div class="alert alert-{}">{}</div>').format(escape(kind), escape(content)))

    class AlertPlugin(ContentTransformerPluginBase):
        """Adds an [alert] shortcode for Bootstrap alert boxes."""

        accepted_content_types: frozenset[ContentType] = frozenset({"post", "page"})
        shortcodes: ClassVar[dict[str, Shortcode]] = {"alert": _AlertShortcode()}

.. _field-rendering:

**Field rendering**

A shortcode's :meth:`~platzky.shortcodes.Shortcode.transform_field_value` method
is called by host applications (such as Goodmap) to transform a structured field
value into a frontend-ready dict, rather than rendering HTML from post content.

To opt a plugin's shortcodes in to field rendering, include ``"field"`` in
``accepted_content_types``:

.. code-block:: python

    class MyPlugin(ContentTransformerPluginBase):
        accepted_content_types: frozenset[ContentType] = frozenset({"post", "page", "field"})

To opt out — for example a purely cosmetic shortcode that has no meaningful field
representation — simply omit ``"field"`` from the set. Host applications must
also grant the plugin permission via ``allowed_content_types`` in the database
config (see :ref:`plugin-configuration`).

**Built-in shortcodes**

Platzky ships two shortcodes that are always available:

``[image url="…" alt="…" width="…" height="…"]``
    Embeds an ``<img>`` tag. ``url`` is required.

``[link url="…" target="…"]text[/link]``
    Creates an ``<a>`` tag. ``url`` is required; ``target="_blank"`` automatically
    adds ``rel="noopener noreferrer"``.

Both reject non-HTTP/HTTPS external URLs and relative paths not starting with ``/``.

Shortcodes are documented for content authors on the admin *Help* page
(``/admin/help``).

Login Plugins
-------------

.. versionadded:: 2.0.0

Declare a ``provider_name`` and implement ``render_login_button`` and
``authenticate``. The login blueprint registers ``/login/verify/<provider>``
which dispatches to the matching plugin.

.. code-block:: python

    from typing import Any, ClassVar
    from flask import Request
    from markupsafe import Markup
    from platzky import LoginPluginBase
    from platzky.auth import AuthenticationError, User

    class GithubLoginPlugin(LoginPluginBase):
        """Login via GitHub OAuth."""

        provider_name: ClassVar[str] = "github"

        def __init__(self, config: dict[str, Any]) -> None:
            super().__init__(config)
            self._client_id = config.get("client_id", "")
            self._client_secret = config.get("client_secret", "")

        def render_login_button(self) -> Markup:
            url = f"https://github.com/login/oauth/authorize?client_id={self._client_id}"
            return Markup(f'<a href="{url}">Login with GitHub</a>')

        def authenticate(self, request: Request) -> User:
            code = (request.get_json() or {}).get("code")
            if not code:
                raise AuthenticationError("Missing OAuth code")
            # exchange code for token, fetch user info …
            return {"username": "example-user"}

HTML Injector Plugins
----------------------

.. versionadded:: 2.0.0

Page decorator plugins inject static HTML into the ``<head>`` or ``<body>`` of
every page. The HTML is captured once at startup — use the plugin's own config
for environment-specific values such as tracking IDs or public keys. Never embed
secrets or credentials in injected HTML.

.. code-block:: python

    from typing import Any
    from platzky import HtmlInjectorPluginBase, PageSection

    class AnalyticsPlugin(HtmlInjectorPluginBase):
        """Inject a Google Analytics snippet into the page head."""

        accepted_page_sections: frozenset[PageSection] = frozenset({"head"})

        def __init__(self, config: dict[str, Any]) -> None:
            super().__init__(config)
            self._tracking_id = config.get("tracking_id", "")

        def get_head_html(self) -> str:
            return (
                f'<script async src="https://www.googletagmanager.com/gtag/js'
                f'?id={self._tracking_id}"></script>'
            )

Override ``get_head_html`` to inject into ``<head>`` and/or ``get_body_html`` to
inject at the start of ``<body>``. Only sections declared in ``accepted_page_sections``
**and** permitted by ``allowed_page_sections`` in the database config are injected —
neither side alone controls what gets rendered.

Packaging a Plugin
------------------

Plugins are discovered via the ``platzky.plugins`` entry-point group. Declare your
plugin class in ``pyproject.toml``:

.. code-block:: toml

    [tool.poetry.plugins."platzky.plugins"]
    my_plugin = "platzky_my_plugin:MyPlugin"

The key (``my_plugin``) is the name used in the database configuration.

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

For content transformer plugins you can restrict which content types are processed.
Include ``"field"`` to also allow the plugin's shortcodes to be used for field
rendering by host applications:

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
(``/admin/help``). Override ``get_info()`` to provide a user-facing name and
description:

.. code-block:: python

    from platzky.plugin.plugin import PluginBase, PluginInfo

    class MyPlugin(PluginBase):
        def get_info(self) -> PluginInfo:
            return PluginInfo(name="My Plugin", description="Does something useful.")

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

