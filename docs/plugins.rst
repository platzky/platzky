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

Platzky's own content types are :data:`platzky.content_types.BUILTIN_CONTENT_TYPES`
— ``"post"``, ``"page"``, ``"comment"``. An application built on platzky adds its
own kinds (see :ref:`new-content-types`), and plugins opt in to those the same way.

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

.. _value-rendering:

**Rendering a stored value**

A shortcode can also render a value the application has stored against a record — rather than
a tag an author wrote in prose — through
:meth:`~platzky.shortcodes.Shortcode.render_value`:

:meth:`~platzky.shortcodes.Shortcode.render_value`
    Renders the value to HTML, so the application needs no per-shortcode frontend
    code at all. It is ``final``: a shortcode has exactly one rendering, in
    ``render``, and this maps a field value onto that method's arguments — keys
    matching declared ``attributes`` become attributes, ``content_key`` (or
    ``value``) becomes the inner content, and a scalar value becomes the inner
    content on its own. So every shortcode gains field rendering without writing
    any, and the tag and the field cannot drift apart.

    A shortcode adapts by *declaring*, not by overriding. If a stored value keeps
    the content under its own key, name it::

        class PromocodeShortcode(Shortcode):
            name = "promocode"
            content_key = "code"          # {"code": "SAVE20"} -> render(attrs, "SAVE20")
            attributes = ShortcodeAttrs([ShortcodeAttr("color", "Button colour")])

    Anything a stored value should be able to override becomes a ``ShortcodeAttr``,
    which content authors then get as a tag attribute too.

An application wanting the value as *data* rather than markup — to render it natively, index
it, or export it — reads the stored entry directly, using ``content_key`` to know
which key a bare value belongs under. Platzky does not shape that payload: only the
application knows what its own wire format needs, and a shortcode describing one would be a
second contract to keep in step with ``render``.

As with a tag written by an author, escaping is ``render``'s responsibility: a stored
value is data and can be hostile. An application that renders the returned HTML is extending
the plugin the same trust platzky extends it in post content, so a shortcode must not
interpolate a stored value without escaping or validating it.

.. _new-content-types:

New content types
~~~~~~~~~~~~~~~~~

Platzky produces posts, pages and comments — ``POST``, ``PAGE``, ``COMMENT`` in
:mod:`platzky.content_types`. An application or plugin with its own kind of content
names its own and registers it:

.. code-block:: python

    MARKER_FIELD: ContentType = "field"

    create_app_from_config(config, extra_content_types=[MARKER_FIELD])

A plugin opts in exactly as it would for a post:

.. code-block:: python

    class MyPlugin(ContentTransformerPluginBase):
        accepted_content_types: frozenset[ContentType] = frozenset({"post", "field"})

and the operator grants it through ``allowed_content_types`` in the database config
(see :ref:`plugin-configuration`); a plugin runs only where both agree. A content type
is only ever its name, so accepting a kind of content never means importing the package
that brought it — otherwise every plugin handling marker fields would depend on the
application that has them.

The vocabulary being open costs static checking: ``ContentType`` is ``str``, and a
closed ``Literal`` cannot survive extension, since platzky cannot know at type-check time
what a package it has never heard of will add. A package that knows its own whole
vocabulary can narrow for its own code::

    GoodmapContentType = Literal["post", "page", "comment", "field"]

A plugin can contribute one too, which is what lets a plugin large enough to bring its
own kind of content install without an application built around it:

.. code-block:: python

    class MarkerPlugin(ContentTransformerPluginBase):
        provides_content_types: ClassVar[frozenset[str]] = frozenset({MARKER_FIELD})

``provides_content_types`` is the counterpart to ``accepted_content_types``: what a
plugin *produces* rather than what it consumes. The two are independent — contributing
a type to the vocabulary is not permission to act on it, which still takes the plugin's
own opt-in and the operator's grant.

Content types are read only when content is transformed, well after loading, so a
plugin may contribute one whatever order it loads in, and the check below runs once
every plugin is loaded rather than as each one arrives.

A plugin naming a type nothing registered is *inert*, not an error — it installs
cleanly and is simply never called with one, which is what lets a single plugin serve
both an application that has the type and a plain platzky blog that does not. Because
such a grant silently does nothing, platzky logs a warning naming the unknown type,
which is usually a typo in operator config.

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

Frontend Overlays
-----------------

.. versionadded:: 2.0.0

To show a toast, dialog, or popover above the page content, render it into the
``#overlay-root`` element — present on every page — instead of into your own
markup. Overlays rendered anywhere else end up below the navbar or below
modals, regardless of their ``z-index``.

.. code-block:: javascript

    const toast = document.createElement("div");
    toast.style.cssText = "position: absolute; top: 50%; inset-inline: 0;";
    document.getElementById("overlay-root").append(toast);

The layer spans exactly the visible content area — the left panel, when one is
shown, is already excluded — so there is nothing to measure at runtime. Both
``position: absolute`` and ``position: fixed`` children resolve their insets
against the layer rather than the viewport, so overlay libraries that default
to ``fixed`` work unmodified.

Rules to keep in mind:

- Scripts in ``<body>`` can look the element up directly. Scripts injected into
  ``<head>`` via ``dynamic_head`` run before ``<body>`` is parsed and must wait
  for ``DOMContentLoaded``.
- Don't size a child to the full layer: the layer is viewport-high, so a
  full-size child covers the navbar and intercepts its clicks.
- Clicks pass through the layer to the page underneath, but each direct child
  takes them. A child that spans the layer blocks clicks across the whole
  content area even where it draws nothing, so give it
  ``pointer-events: none`` and re-enable it on the parts that are visible.

Host-Defined Capabilities
-------------------------

.. versionadded:: 2.0.0

The capability base classes above are platzky's built-in contract. Plugin
*discovery* never injects new capability bases: an installed package cannot add a
capability simply by being present, because each built-in capability carries an
engine-enforced allowlist (notifier topics, content types, page sections) and
auto-injection would let a dependency sidestep it.

An application that *composes* the engine via
:func:`platzky.create_app_from_config` owns its own plugin ecosystem, and may
extend the system for it by passing two arguments:

``extra_plugin_bases``
    Additional capability base classes (``PluginBase`` subclasses) the engine will
    recognise when registering plugins, on top of the built-in ones.

``extra_plugins_entrypoints``
    Additional entry-point groups to discover plugins from, on top of
    ``platzky.plugins``.

.. code-block:: python

    from platzky import create_app_from_config
    from platzky.plugin.plugin import PluginBase

    class MyAppCapabilityBase(PluginBase):
        """A capability owned by the application embedding platzky."""

    app = create_app_from_config(
        config,
        extra_plugin_bases=[MyAppCapabilityBase],
        extra_plugins_entrypoints=["myapp.plugins"],
    )

Plugins that subclass ``MyAppCapabilityBase`` and declare a ``myapp.plugins`` entry
point are then discovered, config-gated (``is_active``), and loaded through the same
loader as platzky's own plugins. The extension is explicit and owned by the embedding
application, not granted to arbitrary installed packages via discovery.

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
rendering by the application:

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

