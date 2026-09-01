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

    from collections.abc import Mapping
    from platzky import ALL_CONTENT_TYPES, ContentTransformerPluginBase, ContentType

    class EmojiPlugin(ContentTransformerPluginBase):
        """Replace :smile: tokens with emoji."""

        accepted_content_types: Mapping[ContentType, str] = {
            ALL_CONTENT_TYPES: "Swaps text for emoji; nothing about it is content-specific.",
        }

        def transform_text(self, text: str) -> str:
            return text.replace(":smile:", "😊")

Override ``transform_text`` to apply plain-text transformations. The framework
guarantees that shortcode tags are excluded from the text passed here and
re-inserted after transformation. ``transform_content`` is ``@final`` and must
not be overridden.

.. _declaring-scope:

Declaring scope
~~~~~~~~~~~~~~~

``accepted_content_types`` maps each content type a plugin asks for to **why it needs
it**. The reason is required — a declaration missing one raises ``ValueError`` when the
class is defined — because it is shown beside the checkbox an operator ticks, and a
justification nothing enforces is one that rots. Declaring nothing at all is still
allowed; such a plugin simply transforms no content.

Two keys have to turn before a transformer runs, and they belong to different people:

``accepted_content_types``
    The plugin author's declaration: the choices an operator is *offered*. Think of the
    checkboxes an admin panel puts on screen.

``allowed_content_types``
    The operator's grant, in the database config (see :ref:`plugin-configuration`):
    which of those checkboxes they ticked.

Silence is refusal on both sides, so declaring broadly never widens what a plugin
actually does — a type nobody granted stays ungranted, and the engine, not the plugin,
decides routing.

Key the declaration with :data:`~platzky.content_types.ALL_CONTENT_TYPES` when the plugin
has no technical constraint on where it runs. One reason then stands for every type it is
offered. The wildcard resolves against the content types the application actually has, so
a plugin written today is offered one invented tomorrow and never hardcodes a name
belonging to a package it does not depend on. It grants nothing on its own — the operator
still names each type.

Enumerate when there is a real constraint. A shortcode that embeds raw markup, reaches an
external host, or costs something to run cannot honestly claim to work anywhere. The
built-in ``[hero]`` tag is the in-tree example: it wraps whatever it is given as raw
markup by design, so its transformer names its types instead:

.. code-block:: python

    from collections.abc import Mapping
    from platzky import ContentTransformerPluginBase
    from platzky.content_types import PAGE, POST, ContentType

    class HeroPlugin(ContentTransformerPluginBase):
        """Wrap content in a hero block."""

        accepted_content_types: Mapping[ContentType, str] = {
            POST: "Wraps a post body in a hero block.",
            PAGE: "Wraps a page body in a hero block.",
        }

Enumerating is **not** how a plugin keeps itself out of comments. Whether commenters may
use a shortcode is the operator's policy — their grant already decides it, and a plugin
narrowing its declaration for that reason only takes away a choice that was theirs to
make.

**Asking the registry**

The gate is
:class:`~platzky.plugin.content_transformer.ContentTransformerRegistry`, reachable as
``app.content_transformers``. Code that renders the operator's choices — an admin panel,
say — asks it rather than reading the plugin's attribute directly:

``acceptable_content_types(plugin)``
    The types this plugin may be granted: its declaration resolved against the
    vocabulary the application actually has, so a wildcard comes back expanded.

``rationale_for(plugin, content_type)``
    The author's reason for that type, to show beside the checkbox.

``may_transform(plugin, content_type)``
    Whether both keys have turned. This is the question the pipeline itself asks.

``grant(plugin, allowed_types)``
    Records the operator's grant. Called by the plugin loader with the plugin's
    ``allowed_content_types``; not intended for plugin code.

``warn_unknown_grants()``
    Logs a warning for each granted content type nothing registered. Run once, after
    every plugin has loaded.

Shortcodes
~~~~~~~~~~

Content transformer plugins can also register *shortcodes* — bracket-style tags
that content authors embed in content, and that an application can also use to render
a value it has stored (see :ref:`Rendering a stored value <value-rendering>`).

**Syntax**

.. code-block:: text

    [tagname attr="val"]              # void (no inner content)
    [tagname attr="val"]content[/tagname]  # block

Declare ``shortcodes`` as a class variable:

.. code-block:: python

    from collections.abc import Mapping
    from typing import ClassVar
    from markupsafe import escape
    from platzky import ALL_CONTENT_TYPES, ContentTransformerPluginBase, ContentType
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
            # content is embedded as-is; only the attribute is escaped. See "Escaping" below.
            return f'<div class="alert alert-{escape(kind)}">{content}</div>'

    class AlertPlugin(ContentTransformerPluginBase):
        """Adds an [alert] shortcode for Bootstrap alert boxes."""

        accepted_content_types: Mapping[ContentType, str] = {
            ALL_CONTENT_TYPES: "Renders an alert box; nothing about it is content-specific.",
        }
        shortcodes: ClassVar[dict[str, Shortcode]] = {"alert": _AlertShortcode()}

The plugin's ``accepted_content_types`` decides where its shortcodes may be used; see
:ref:`declaring-scope` above.

**Built-in shortcodes**

Platzky ships three shortcodes that are always available, registered by a built-in
transformer that runs ahead of any plugin:

``[image url="…" alt="…" width="…" height="…"]``
    Embeds an ``<img>`` tag. ``url`` is required.

``[link url="…" target="…"]text[/link]``
    Creates an ``<a>`` tag. ``url`` is required; ``target="_blank"`` automatically
    adds ``rel="noopener noreferrer"``.

``[hero]…[/hero]``
    Wraps its content in a ``<div class="hero">`` header block, anywhere in the body.

``[image]`` and ``[link]`` reject non-HTTP/HTTPS external URLs and relative paths not
starting with ``/``. All three are granted ``POST`` and ``PAGE`` only — ``[hero]`` embeds
its content as raw markup, so the built-in transformer enumerates rather than claiming to
suit any kind of content.

Shortcodes are documented for content authors on the admin *Help* page
(``/admin/help``).

**Escaping**

Two rules, and they do not vary by shortcode:

*Embed* ``content`` *directly. Never escape it.*
    It is already safe by the time you see it. Content reaching
    :meth:`~platzky.engine.Engine.transform_content` is escaped on the way in unless the
    caller vouched for it by passing ``Markup`` — as ``blog.py`` does for a post body,
    which an author with write access wrote — and a stored value rendered through
    ``render_value`` is escaped there, because nobody vouched for it. Anything the
    pipeline added since came from a plugin that was granted this content type, so it is
    markup platzky itself produced.

    Escaping it again is what makes a nested shortcode's output, or a text filter's, show
    up as literal ``&lt;span&gt;`` on the page.

*Escape every attribute where you interpolate it.*
    Attributes arrive raw. That escaping is an HTML-attribute-context obligation rather
    than a trust judgement, so it applies just as much to a value an author typed as to
    one out of a database.

A caller handing platzky content it did not write should pass a plain ``str`` and let the
boundary escape it. Vouching is the deliberate act; the default is the safe one.

.. _value-rendering:

**Rendering a stored value**

A shortcode can also render a value the application has stored against a record — rather than
a tag an author wrote in prose — through
:meth:`~platzky.shortcodes.shortcode.Shortcode.render_value`:

:meth:`~platzky.shortcodes.shortcode.Shortcode.render_value`
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

Take the shortcodes to render with from :meth:`~platzky.engine.Engine.shortcodes_for`, not
by reading ``shortcodes`` off loaded plugins::

    for name, shortcode in app.shortcodes_for("field").items():
        ...

``render_value`` is called directly by the application and so does not pass through
``transform_content``, where routing is normally enforced. ``shortcodes_for`` applies the
same two keys that pipeline applies — the plugin's own ``accepted_content_types`` and the
operator's ``allowed_content_types`` grant — so an operator withholding a content type
withholds it here too. Collecting shortcodes off ``loaded_plugins`` instead would leave
the grant governing prose but not stored values.

An application wanting the value as *data* rather than markup — to render it natively, index
it, or export it — reads the stored entry directly, using ``content_key`` to know
which key a bare value belongs under. Platzky does not shape that payload: only the
application knows what its own wire format needs, and a shortcode describing one would be a
second contract to keep in step with ``render``.

The escaping rules above hold unchanged here, and a shortcode needs no second code path
for them. A stored value is data and nobody vouched for it, so ``render_value`` escapes
the content before calling ``render`` — exactly what ``transform_content`` does for
unvouched prose. ``render`` therefore embeds its ``content`` directly on both paths, and
escapes each attribute where it interpolates it, since attributes out of a stored value
arrive raw just as a tag's do.

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
        accepted_content_types: Mapping[ContentType, str] = {
            POST: "Renders its tags in post bodies.",
            MARKER_FIELD: "Renders the same tags stored against a marker.",
        }

A plugin with no constraint on where it runs need not name the new type at all: keying
its declaration with ``ALL_CONTENT_TYPES`` offers whatever the application has, including
types added after the plugin was written (see :ref:`declaring-scope`).

Either way the operator grants it through ``allowed_content_types`` in the database config
(see :ref:`plugin-configuration`); a plugin runs only where both agree. A content type
is only ever its name, so accepting a kind of content never means importing the package
that brought it — otherwise every plugin handling marker fields would depend on the
application that has them.

The vocabulary being open costs static checking: ``ContentType`` is ``str``, and a closed
``Literal`` cannot survive extension, since platzky cannot know at type-check time what a
package it has never heard of will add. A name is therefore checked at runtime or not at
all — an operator's grant naming a type nothing produces is reported at startup by
``warn_unknown_grants``.

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

