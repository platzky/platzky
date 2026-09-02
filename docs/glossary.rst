Glossary
========

Platzky's documentation and its docstrings lean on a small vocabulary, mostly about *who
decides what*. The terms are defined once here and used consistently everywhere else.

.. glossary::
   :sorted:

   site owner
      The person who runs a particular site: they own ``config.yml`` and the plugin
      configuration in the database, tick which :term:`content types <content type>` a
      plugin may act on (its :term:`grant`), and turn :term:`feature flags <feature flag>`
      on and off. Not the person who wrote the plugin and not the person who writes the
      posts, though on a small site all three may be the same human. When the docs say a
      decision is the site owner's, they mean it is made in configuration and neither
      platzky nor a plugin may make it for them.

   author
      Someone with CMS write access, who writes posts and pages. Their content is
      :term:`vouched <vouching>` for by the code that loads it, so the HTML they write
      renders as HTML — unless the site owner turned on ``STRIP_CONTENT_HTML``.

   commenter
      A visitor who submits a comment. Nobody vouches for what they write, so it is
      escaped at the boundary and reaches the page as text. A commenter is the reason
      malformed shortcode tags are not an error in unvouched content: a stranger's typo
      must not take a page down.

   plugin author
      The author of a ``platzky_<name>`` package. They write a :term:`content transformer`
      or another :term:`capability base` subclass, and :term:`declare <declaration>` what
      their plugin needs — but they cannot grant it to themselves.

   application
      The package that builds a platzky app by calling ``create_app`` or
      ``create_app_from_config`` — goodmap is one. An application may bring its own
      blueprints, :term:`content types <content type>` and plugin bases, and is the layer
      that knows where a piece of content came from, which is what puts it in a position
      to :term:`vouch <vouching>` for it.

   engine
      :class:`~platzky.engine.Engine`, the Flask subclass every platzky app is an instance
      of. It holds the plugins, the notifiers, the login methods and the content-transformer
      registry, and it — not a plugin — decides routing.

   content type
      The name of a kind of content: platzky's own ``"post"``, ``"page"`` and
      ``"comment"``, or one an :term:`application` brings for content platzky has no
      concept of (see :ref:`new-content-types`). The vocabulary is open and a content type
      is just its name, so a plugin can accept a kind of content without importing the
      package that brought it.

   declaration
      A plugin's ``accepted_content_types``: which :term:`content types <content type>` it
      is willing to act on, each mapped to *why*. It is an offer, not a decision — the set
      of checkboxes an :term:`site owner` is shown. Widening it never widens what the plugin
      actually does.

   grant
      A plugin's ``allowed_content_types``, set by the :term:`site owner` in the plugin's
      database configuration: which of the offered :term:`content types <content type>`
      they ticked. Silence is refusal — an ungranted type stays ungranted.

   offer and grant
      The rule that a :term:`content transformer` runs on a piece of content only where its
      :term:`declaration` (the offer) and the :term:`site owner`\ 's :term:`grant` agree.
      The two belong to different people on purpose, which is why neither alone is enough.

   vouching
      Asserting that content came from someone with write access, by passing it as
      ``Markup`` rather than ``str``. Only the caller knows a piece of content's
      provenance, so vouching is a deliberate act and plain ``str`` is treated as hostile
      and escaped. Vouched content is also parsed strictly: whoever wrote a malformed tag
      can go and fix it.

   content transformer
      A plugin subclassing
      :class:`~platzky.plugin.content_transformer.ContentTransformerPluginBase`. It
      contributes a text filter (``transform_text``) and any number of
      :term:`shortcodes <shortcode>`, and runs only where :term:`offer and grant` agree.

   shortcode
      A bracket-style tag an :term:`author` writes in content — ``[image url="…"]``,
      ``[html]…[/html]`` — that a :term:`content transformer` registers and renders. Also
      usable to render a value the application has stored, through ``render_value``.

   shortcode kind
      A shortcode's ``block`` / ``void`` / ``raw`` declaration, read by the parser *before*
      it descends into the tag. It decides whether a closing tag is expected and what
      happens to the text between the tags; ``render`` runs afterwards and so cannot
      influence it.

   raw body
      The text between the tags of a ``raw`` :term:`shortcode`. It is lifted out of the
      document whole: no shortcode inside it renders, no text filter reaches it, and
      ``STRIP_CONTENT_HTML`` does not remove HTML from it. That is what makes ``[html]``
      the way an author marks markup they mean.

   feature flag
      A :class:`~platzky.feature_flags.FeatureFlag` the :term:`site owner` switches under
      ``FEATURE_FLAGS`` in the config, checked with ``engine.is_enabled(flag)``.

   capability base
      A plugin base class naming what a plugin can do — notifier, content transformer,
      login method, HTML injector. A plugin is recognised by which bases it subclasses, so
      one plugin may provide several capabilities.
