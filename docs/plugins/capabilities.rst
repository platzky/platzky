Other Plugin Capabilities
=========================

The capabilities beyond content transformation: notifications, login providers,
injected HTML, and the bases an embedding application defines for itself.

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

