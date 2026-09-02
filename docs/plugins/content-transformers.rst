Content Transformer Plugins
===========================

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

Override ``transform_text`` to apply plain-text transformations. What reaches it is only
what an author typed between tags: never a shortcode's attributes, never another
shortcode's output, and never the body of a ``raw`` tag. It is the only method a
transformer implements: running one is the registry's job, reached through
``Engine.transform_content``, which parses the whole document once, then runs every
permitted filter, then renders every permitted tag. A transformer does not control that
sequence for itself, and has no way to run outside the :term:`site owner`\ 's :term:`grant`.

A transformer's other half is :doc:`shortcodes` — named tags it registers, rendered by
the same pass. This page covers where a transformer is allowed to run; that one covers
what its tags emit.

Jinja extensions
----------------

A content transformer may also contribute Jinja2 extensions, which are collected at
startup and registered on the engine's template environment. Use this for template-level
syntax — a custom tag or filter available in every template — as opposed to
``transform_text`` and shortcodes, which act on stored content:

.. code-block:: python

    class MyPlugin(ContentTransformerPluginBase):
        def get_jinja_extensions(self) -> list[type[jinja2.ext.Extension]]:
            return [MyExtension]

Extensions are gathered from every loaded transformer regardless of
``accepted_content_types``: :term:`offer and grant` governs *content*, and a Jinja extension
is not content. An extension therefore reaches every template the application renders, so
a plugin should contribute one only when that is genuinely what it means.

.. _transformer-order:

Order
-----

Transformers are a pipeline: each one's output is the next one's input, the way
``cat post | emoji | red_letter`` would be. Order therefore changes the result, and the
order is **the order the plugins appear in the site owner's config**, because the loader
walks the ``plugins`` object top to bottom and each plugin is appended as it loads.

.. code-block:: text

    {"plugins": {"emoji": {…}, "red_letter": {…}}}

is ``emoji | red_letter``; swapping the two keys swaps the stages. Platzky's built-in
shortcode transformer is the one exception — it is always inserted first, so ``[image]``,
``[link]`` and ``[hero]`` have rendered before any plugin runs.

Two consequences worth knowing:

*A transformer sees what earlier ones produced, markup included.*
    By the time a later plugin's ``transform_text`` runs, earlier stages have already
    rendered their shortcodes to HTML. The framework keeps tags away from
    ``transform_text``, so a filter does not corrupt them, but they are in the content.

*A failing transformer aborts the chain.*
    Stages are not independent, so a stage that raises stops the pipeline rather than
    passing partial output to the next one.

*Two plugins claiming one tag name: the earlier wins.*
    Prose has no other option — the first transformer to own a tag renders it, so the
    later one never sees it. :meth:`~platzky.engine.Engine.shortcodes_for` and the admin
    help page follow the same rule, so a stored value renders exactly as the identical tag
    in a post body would. The loser is logged at startup, naming both plugins.

Nothing sorts or prioritises the pipeline: a site owner who needs a particular order gets
it by ordering the config keys. A plugin cannot request a position, and built-in
shortcodes are registered ahead of every plugin, so ``[image]``, ``[link]`` and ``[hero]``
cannot be displaced.

.. _declaring-scope:

Declaring scope
---------------

``accepted_content_types`` maps each :term:`content type` a plugin asks for to **why it
needs it**. The reason is required — a declaration missing one raises ``ValueError`` when the
class is defined — because it is shown beside the checkbox a site owner ticks, and a
justification nothing enforces is one that rots. Declaring nothing at all is still
allowed; such a plugin simply transforms no content.

Two people have to agree before a transformer runs — the plugin author offers, the site
owner grants:

``accepted_content_types``
    The plugin author's declaration: the choices a site owner is *offered*. Think of the
    checkboxes an admin panel puts on screen.

``allowed_content_types``
    The site owner's grant, in the database config (see :ref:`plugin-configuration`):
    which of those checkboxes they ticked.

Silence is refusal on both sides, so declaring broadly never widens what a plugin
actually does — a type nobody granted stays ungranted, and the engine, not the plugin,
decides routing.

Key the declaration with :data:`~platzky.content_types.ALL_CONTENT_TYPES` when the plugin
has no technical constraint on where it runs. One reason then stands for every type it is
offered. The wildcard resolves against the content types the application actually has, so
a plugin written today is offered one invented tomorrow and never hardcodes a name
belonging to a package it does not depend on. It grants nothing on its own — the site owner
still names each type.

Name each type instead when there is a real constraint. A shortcode that emits
block-level layout markup, reaches an external host, or costs something to run cannot
honestly claim to work anywhere. The built-in ``[hero]`` tag is the in-tree example: it
wraps what it is given in a ``<div class="hero">``, a header block that only makes sense
in a document body, so its transformer names the two types where that is true:

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

Naming types is **not** how a plugin keeps itself out of comments. Whether commenters may
use a shortcode is the site owner's policy — their grant already decides it, and a plugin
narrowing its declaration for that reason only takes away a choice that was theirs to
make.

**Asking the registry**

The gate is
:class:`~platzky.plugin.content_transformer.ContentTransformerRegistry`, reachable as
``app.content_transformers``. Code that renders the site owner's choices — an admin panel,
say — asks it rather than reading the plugin's attribute directly:

``acceptable_content_types(plugin)``
    The types this plugin may be granted: its declaration resolved against the
    vocabulary the application actually has, so a wildcard comes back expanded.

``rationale_for(plugin, content_type)``
    The author's reason for that type, to show beside the checkbox.

``may_transform(plugin, content_type)``
    Whether the offer and the grant agree. This is the question the pipeline itself asks.

``grant(plugin, allowed_types)``
    Records the site owner's grant. Called by the plugin loader with the plugin's
    ``allowed_content_types``; not intended for plugin code.

``warn_unknown_grants()``
    Logs a warning for each granted content type nothing registered. Run once, after
    every plugin has loaded.

.. _new-content-types:

New content types
-----------------

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

Either way the site owner grants it through ``allowed_content_types`` in the database config
(see :ref:`plugin-configuration`); a plugin runs only where both agree. A content type
is only ever its name, so accepting a kind of content never means importing the package
that brought it — otherwise every plugin handling marker fields would depend on the
application that has them.

The vocabulary being open costs static checking: ``ContentType`` is ``str``, and a closed
``Literal`` cannot survive extension, since platzky cannot know at type-check time what a
package it has never heard of will add. A name is therefore checked at runtime or not at
all — a site owner's grant naming a type nothing produces is reported at startup by
``warn_unknown_grants``.

A plugin can contribute one too, which is what lets a plugin large enough to bring its
own kind of content install without an application built around it:

.. code-block:: python

    class MarkerPlugin(ContentTransformerPluginBase):
        provides_content_types: ClassVar[frozenset[str]] = frozenset({MARKER_FIELD})

``provides_content_types`` is the counterpart to ``accepted_content_types``: what a
plugin *produces* rather than what it consumes. The two are independent — contributing
a type to the vocabulary is not permission to act on it, which still takes the plugin's
own opt-in and the site owner's grant.

Content types are read only when content is transformed, well after loading, so a
plugin may contribute one whatever order it loads in, and the check below runs once
every plugin is loaded rather than as each one arrives.

A plugin naming a type nothing registered is *inert*, not an error — it installs
cleanly and is simply never called with one, which is what lets a single plugin serve
both an application that has the type and a plain platzky blog that does not. Because
such a grant silently does nothing, platzky logs a warning naming the unknown type,
which is usually a typo in site-owner config.

