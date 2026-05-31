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

Since 1.5.0, plugins are built around *capability base classes*. Pick the one that
matches what your plugin does:

.. plugin-capabilities::

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

Subclass ``NotifierPluginBase`` to send notifications. Declare which topics your
plugin handles via ``accepted_topics``; the engine routes notifications to matching
plugins only.

The three built-in topics are ``"security"``, ``"content"``, and ``"general"``.

.. code-block:: python

    from typing import Any
    from platzky import NotifierPluginBase, NotificationTopic

    class SlackNotifier(NotifierPluginBase):
        """Send notifications to a Slack channel."""

        accepted_topics: frozenset[NotificationTopic] = frozenset({"general", "security"})

        def __init__(self, config: dict[str, Any]) -> None:
            super().__init__(config)
            self._webhook = config.get("webhook_url", "")

        def notify(self, message: str, topic: NotificationTopic, receiver: str = "") -> None:
            # post to self._webhook …
            pass

**With attachments**

Subclass ``AttachmentNotifierPluginBase`` instead when your plugin needs to handle
files. Implement ``notify_with_attachments``; the base class delegates plain
``notify`` calls to it with an empty attachment list automatically.

.. code-block:: python

    from collections.abc import Sequence
    from typing import Any
    from platzky import AttachmentNotifierPluginBase, NotificationTopic
    from platzky.attachment import AttachmentProtocol

    class MailNotifier(AttachmentNotifierPluginBase):
        """Email notifier with attachment support."""

        accepted_topics: frozenset[NotificationTopic] = frozenset({"content"})

        def __init__(self, config: dict[str, Any]) -> None:
            super().__init__(config)
            self._to = config.get("recipient", "")

        def notify_with_attachments(
            self,
            message: str,
            topic: NotificationTopic,
            attachments: Sequence[AttachmentProtocol],
            receiver: str = "",
        ) -> None:
            # send email …
            pass

Content Transformer Plugins
---------------------------

.. versionadded:: 1.5.0

Subclass ``ContentTransformerPluginBase`` to modify post, page, or comment content
before rendering. Declare which content types to process via ``accepted_content_types``.

The three content types are ``"post"``, ``"page"``, and ``"comment"``.

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

Subclass ``LoginPluginBase`` to add a login provider to the admin panel.
Declare a ``provider_name`` (used as the URL segment) and implement
``get_login_method`` (renders the button HTML) and ``authenticate``
(validates the incoming request and returns user info).

The engine automatically registers a ``/verify_login/<provider>`` route
that dispatches to the matching plugin, so no Flask blueprint is needed.

.. code-block:: python

    from collections.abc import Callable
    from typing import Any, ClassVar
    from flask import Request
    from platzky import LoginPluginBase
    from platzky.auth import AuthenticationError, User

    class GithubLoginPlugin(LoginPluginBase):
        """Login via GitHub OAuth."""

        provider_name: ClassVar[str] = "github"

        def __init__(self, config: dict[str, Any]) -> None:
            super().__init__(config)
            self._client_id = config.get("client_id", "")
            self._client_secret = config.get("client_secret", "")

        def get_login_method(self) -> Callable[[], str]:
            client_id = self._client_id
            def render() -> str:
                return f'<a href="https://github.com/login/oauth/authorize?client_id={client_id}">Login with GitHub</a>'
            return render

        def authenticate(self, request: Request) -> User:
            code = (request.get_json() or {}).get("code")
            if not code:
                raise AuthenticationError("Missing OAuth code")
            # exchange code for token, fetch user info …
            return {"username": "example-user"}

Packaging a Plugin
------------------

Plugins are discovered via the ``platzky.plugins`` entry-point group. Declare your
plugin class in ``pyproject.toml``:

.. code-block:: toml

    [tool.poetry.plugins."platzky.plugins"]
    my_plugin = "platzky_my_plugin:MyPlugin"

The key (``my_plugin``) is the name used in the database configuration.

Plugin Configuration
--------------------

After the package is installed, activate the plugin by adding it to the ``plugins``
list in your database:

.. code-block:: json

    {
        "plugins": [
            {
                "name": "my_plugin",
                "config": { "api_key": "abc123" }
            }
        ]
    }

The ``config`` object is passed as a ``dict[str, Any]`` to the plugin's ``__init__``.

For notifier plugins you can restrict which topics the plugin receives:

.. code-block:: json

    {
        "name": "slack_notifier",
        "config": { "webhook_url": "https://hooks.slack.com/…" },
        "allowed_topics": ["security", "general"]
    }

For content transformer plugins you can restrict which content types are processed:

.. code-block:: json

    {
        "name": "alert_plugin",
        "config": {},
        "allowed_content_types": ["post", "page"]
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

Listing Installed Plugins
--------------------------

``discover_plugins()`` returns all plugins installed in the current environment,
regardless of which ones are active in the database:

.. code-block:: python

    from platzky import discover_plugins

    for name, cls in discover_plugins().items():
        print(name, cls)

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

Legacy Plugins
--------------

.. deprecated:: 1.2.0
    Module-style legacy plugins are deprecated and will be removed in 2.0.0.
    Use a class-based capability subclass instead.

Legacy plugins are plain modules with a ``process`` function:

.. code-block:: python

    def process(app, config):
        return app

This style does not support configuration validation, translation discovery, or
capability routing. Migrate to a class-based subclass.
