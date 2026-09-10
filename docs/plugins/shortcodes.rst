Shortcodes
==========

Shortcodes are bracket-style tags that content authors embed in content, and that an
application can also use to render a value it has stored (see
:ref:`Rendering a stored value <value-rendering>`).

They are registered by :doc:`content transformer plugins <content-transformers>` and run
inside ``transform_content``, so everything on that page applies here: a shortcode renders
only where its plugin's ``accepted_content_types`` and the site owner's
``allowed_content_types`` agree (see :ref:`declaring-scope`).

**Syntax**

.. code-block:: text

    [tagname attr="val"]                     # kind = "void"
    [tagname attr="val"]content[/tagname]    # kind = "block"  (the default)
    [tagname]anything at all[/tagname]       # kind = "raw"

A shortcode declares which shape it is, and the parser holds authors to it::

    class ImageShortcode(Shortcode):
        name = "image"
        kind = "void"

``"block"``
    Wraps content, which is parsed for further shortcodes. The default, and the safer one
    to leave in place by mistake: a block shortcode that never declares anything still
    works, whereas a void one wrongly left as ``"block"`` makes every correct use of it
    look unclosed.

``"void"``
    Takes no closing tag, like ``[image url="…"]``. Rendered on sight.

``"raw"``
    Takes a closing tag, but its body is verbatim: brackets inside are characters, not
    syntax, so an author can write *about* a shortcode rather than invoking one. Nothing
    in the pipeline reaches inside: not another plugin's filter, not another plugin's
    shortcodes, not ``STRIP_CONTENT_HTML``. The built-in ``[html]`` is the one in tree;
    ``[latex]`` or ``[mermaid]`` would want the same.

**Malformed tags are reported.** A tag that is never closed, and a closing tag that closes
nothing, both raise :class:`~platzky.shortcodes.shortcode.ShortcodeError` naming the tag
and the character it was written at. Neither has a rendering that is not a guess about
what the author meant, and guessing quietly drops or reparents their content.

Two things are deliberately *not* errors. A tag name no plugin registered passes through
as written — platzky has no opinion on a name it does not know. And content nobody
:term:`vouched <vouching>` for is parsed leniently, because escaping mangles its tags on
the way in: the quotes in
``[wrap tone="loud"]`` become entities, the opening tag stops matching, and its closing tag
is left with nothing to close. Parsed strictly, anyone able to write a comment could fail a
page render by using a shortcode perfectly correctly.

Verbatim means verbatim, HTML included. A raw body is taken out of the document before
any filter or stripping pass runs, so HTML written inside one reaches the page as HTML
even where ``STRIP_CONTENT_HTML`` is removing the HTML around it — which is what makes
``[html]`` the way an author marks a piece they mean. The hatch belongs to whoever the
caller vouched for: content nobody vouched for is escaped at the boundary, raw bodies
with it, so a raw shortcode is never a way to get markup out of a stranger's text.

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
:ref:`declaring-scope`.

**Built-in shortcodes**

Platzky ships six shortcodes that are always available, registered by a built-in
transformer that runs ahead of any plugin:

``[image url="…" alt="…" width="…" height="…"]``
    Embeds an ``<img>`` tag. ``url`` is required. Void — no closing tag.

``[link url="…" target="…" rel="…"]text[/link]``
    Creates an ``<a>`` tag. ``url`` is required; ``target="_blank"`` automatically
    adds ``rel="noopener noreferrer"``.

    ``rel`` takes space-separated tokens from a fixed allowlist — ``sponsored``,
    ``nofollow``, ``ugc``, ``noopener``, ``noreferrer`` — and is unioned with whatever
    ``target="_blank"`` already forces, never a replacement for it. Use ``sponsored`` for
    affiliate and paid links: an undisclosed one is a Search Essentials violation. A token
    outside the allowlist is dropped and the rest of the link still renders, because ``rel``
    is a disclosure a site makes about itself and a typo must not silently become one.

``[hero]…[/hero]``
    Wraps its content in a ``<div class="hero">`` header block, anywhere in the body.

``[slideshow interval="…"]…[/slideshow]``
    Wraps frames in a ``<div class="slideshow">`` that cross-fades between them, and
    rotates up to four. A frame is either a bare image or a ``[figure]``, which lets a
    picture travel together with the text beside it.
    ``interval`` is the milliseconds each slide is shown, defaulting to
    4000 and clamped to 1500–60000; below roughly the floor a cross-fade reads as a flash
    rather than a transition, which is a seizure risk and not a matter of taste. An
    unparseable or out-of-range value is corrected and logged rather than raised, since one
    mistyped attribute should not take a page down.

    The rotation is **pure CSS** — platzky ships no JavaScript of its own. It pauses on
    hover and on focus, and ``prefers-reduced-motion: reduce`` turns each dissolve into a
    cut while leaving the rotation running, the rotation being content rather than
    decoration. Wrapping more than four images is not an error: the stylesheet has no
    timings for that count, so they render as an ordinary sequence, because a missing rule
    must never be able to hide an image somebody wrote.

``[figure]…[/figure]``
    A picture with the text that belongs beside it: the image floats and the rest flows
    around it. Useful on its own, and it is also what a ``[slideshow]`` rotates — wrapped
    there, the whole frame counts as a single slide however many images are inside::

        [slideshow interval="4000"]
          [figure][image url="/one.jpg" alt="…"]This is the first chapter.[/figure]
          [figure][image url="/two.jpg" alt="…"]This is the second.[/figure]
        [/slideshow]

    Because the text flows rather than being laid out as a separate box, a caption
    containing a link or an emphasis stays one run of prose. Without ``[figure]``, each image
    inside a ``[slideshow]`` is a frame on its own — the right shape for a slideshow of
    nothing but pictures, and still what happens if no ``[figure]`` is used.

    Written outside a ``[slideshow]`` it is simply that layout, with nothing rotating —
    which is why it is named for what it is rather than for the one place it is most
    used. It renders a ``<div class="platzky-figure">``; the class is prefixed because
    Bootstrap already defines ``.figure``.

    Inside a slideshow, every frame shares the box of the first one, which stays in normal
    flow and sizes the slideshow; the rest are laid over it. Frames of very different sizes will therefore be
    constrained to the first one's, so make them alike.

``[html]…[/html]``
    Emits its content exactly as written. Raw, so a shortcode written inside is displayed
    rather than rendered — this is how to document a tag without invoking it — no text
    filter reaches in to rewrite it, and the HTML in it survives ``STRIP_CONTENT_HTML``.

``[image]`` and ``[link]`` accept ``http``/``https`` URLs and paths rooted at ``/``, and
nothing else. A bare relative path such as ``photo.jpg`` is refused because it resolves
against whichever page happens to be showing the content; ``//host/path`` is refused
because it carries no scheme yet is external anyway; every other scheme is refused, which
is what keeps ``javascript:`` and ``data:`` out.

**A tag whose URL is missing or refused renders nothing, and logs why.** An image with no
source is not an image, and ``<img src="">`` is worse than an absence — it draws a broken
icon, and several browsers resolve the empty source against the current page and fetch the
document a second time. ``[link]`` drops its text along with the tag, since link text is
written to be clicked and reads as a mistake when left stranded in prose. The log is the
only trace either leaves, because nobody can see an absence.

All four are granted ``POST`` and ``PAGE`` only — ``[hero]`` emits a ``<div class="hero">``
header block, which only makes sense in a document body, so the built-in transformer names
its types rather than claiming to suit any kind of content.

Shortcodes are documented for content authors on the admin *Help* page
(``/admin/help``).

**Escaping**

Two rules, and they do not vary by shortcode:

.. code-block:: python

    def render(self, attrs: ShortcodeAttrs, content: Markup) -> str:
        kind = attrs.type or "info"
        return f'<div class="alert alert-{escape(kind)}">{content}</div>'
        #                                 ^^^^^^^^^^^^   attribute — always escape
        #                                                 ^^^^^^^   content — never escape

*Embed* ``content`` *directly. Never escape it.*
    Its type is the reason: ``Markup`` means the escaping *decision* has already been
    taken. Not that escaping happened — for a post body it deliberately did not.

*Escape every attribute where you interpolate it.*
    Attributes arrive raw. That is an HTML-attribute-context obligation rather than a
    trust judgement, so it applies just as much to a value an author typed as to one out
    of a database.

**Where ``content`` comes from.** Exactly three sources, and each is settled before
``render`` runs:

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Source
     - Decided by
     - What arrives
   * - The caller's own content
     - ``blog.py`` vouches for a post body with ``Markup``; ``render_value`` escapes a
       stored value; anything else unvouched is escaped
     - live markup if vouched, entities if not
   * - A text filter's output
     - the plugin's ``transform_text``, one step earlier in the same pipeline
     - live markup
   * - An inner shortcode's output
     - a nested tag, already rendered by the time the outer one runs
     - live markup

The last two are markup platzky itself produced, by plugins whose offer and grant both
cover this content type — so trusting them is the same act as granting the plugin.

That is what makes escaping here pointless at best. Every character is either one the
boundary already turned into an entity, leaving nothing to neutralise, or one a trusted
source meant to render, which escaping would destroy.

Concretely: suppose a text filter is installed that colours the letter ``a`` red, and an
author writes ``[alert type="warning"]danger[/alert]``:

.. code-block:: text

    content argument   d<span style="color:red">a</span>nger    <- the filter already ran
    embedding it       <div class="alert alert-warning">d<span style="color:red">a</span>nger</div>
    escaping it        <div class="alert alert-warning">d&lt;span style=&#34;color…nger</div>

The second is the bug: the filter's markup is shown to the reader as literal text. The
same happens to a nested shortcode's output, because by the time the outer shortcode runs
the inner one has already rendered.

Now the same shortcode rendering a *stored* value that is hostile:

.. code-block:: text

    database column    <img src=x onerror=alert(1)>
    content argument   &lt;img src=x onerror=alert(1)&gt;    <- render_value escaped it
    embedding it       <div class="alert alert-info">&lt;img src=x onerror=alert(1)&gt;</div>

Embedding is right in both cases, and only the boundary changed. A post body is vouched
for by ``blog.py``, which passes ``Markup`` because an author with write access wrote it;
a stored value is escaped by ``render_value``, because nobody vouched for a database
column. Anything the pipeline added in between — a filter's output, an inner shortcode's —
came from a plugin granted this content type, so it is markup platzky itself produced.

Attributes get no such treatment, which is why the second rule differs. A hostile ``type``
attribute is defused only by the ``escape`` at the interpolation site::

    <div class="alert alert-&#34; onmouseover=alert(1) x=&#34;">hi</div>

A caller handing platzky content it did not write should pass a plain ``str`` and let the
boundary escape it. Vouching is the deliberate act; the default is the safe one.

.. _value-rendering:

**Rendering a stored value**

A shortcode is normally a tag an :term:`author` writes in prose. It can also render a value
the :term:`application` has stored against a record, where nobody wrote brackets at all —
a field on a product, a map marker's popup entry — through
:meth:`~platzky.shortcodes.shortcode.Shortcode.render_value`. Two ways in, one rendering::

    [promocode color="red"]SAVE20[/promocode]        # written in a post body

    shortcode.render_value({"code": "SAVE20", "color": "red"})   # stored on a record

Both reach the same ``render`` and produce the same
``<span class="promo red">SAVE20</span>``. In the tag, the brackets say which part is the
content and which is an attribute; a stored value has no brackets to say it, so
``content_key`` and ``attributes`` say it instead. That is all the declaring below is for:

:meth:`~platzky.shortcodes.shortcode.Shortcode.render_value`
    Renders the value to HTML, so the application needs no per-shortcode frontend
    code at all. It is ``final``: a shortcode has exactly one rendering, in
    ``render``, and this maps a field value onto that method's arguments — keys
    matching declared ``attributes`` become attributes, ``content_key`` (or
    ``value``) becomes the inner content, and a scalar value becomes the inner
    content on its own. So every shortcode gains field rendering without writing
    any, and the tag and the field cannot drift apart.

    A shortcode adapts to the shape of the stored value by *declaring*, never by
    overriding — ``render_value`` cannot be overridden, so what you change is which
    key holds the content and which keys are attributes. A promo code the application
    stores as ``{"code": "SAVE20", "color": "red"}`` needs no code, only::

        class PromocodeShortcode(Shortcode):
            name = "promocode"
            content_key = "code"          # {"code": "SAVE20"} -> render(attrs, "SAVE20")
            attributes = ShortcodeAttrs([ShortcodeAttr("color", "Button colour")])

    ``content_key`` names the key holding the body. It is ``"content"`` by default and
    ``"value"`` is always accepted as well, so an application storing a bare string needs
    no declaration at all. Anything a stored value should be able to override becomes a
    ``ShortcodeAttr``, which content authors then get as a tag attribute too.

    Given that declaration and a ``render`` of
    ``f'<span class="promo {escape(attrs.color)}">{content}</span>'`` — the attribute
    escaped, the content embedded — here is what each shape of stored value produces:

    .. list-table::
       :header-rows: 1
       :widths: 38 30 32

       * - Stored value
         - ``render`` receives
         - Output
       * - ``"SAVE20"``
         - ``attrs``: nothing, ``content``: ``SAVE20``
         - ``<span class="promo ">SAVE20</span>``
       * - ``{"code": "SAVE20"}``
         - the same — ``content_key`` found it
         - ``<span class="promo ">SAVE20</span>``
       * - ``{"code": "SAVE20", "color": "red"}``
         - ``attrs.color``: ``red``, ``content``: ``SAVE20``
         - ``<span class="promo red">SAVE20</span>``
       * - ``{"code": "SAVE20", "size": "big"}``
         - ``size`` is dropped: no ``ShortcodeAttr`` declares it
         - ``<span class="promo ">SAVE20</span>``
       * - ``{"value": "SAVE20"}``
         - ``value`` is accepted whatever ``content_key`` says
         - ``<span class="promo ">SAVE20</span>``
       * - ``{"colour": "red"}``
         - nothing matches; ``content`` is empty and ``attrs.color`` defaults to ``""``
         - ``<span class="promo "></span>``
       * - ``{"code": "<b>x</b>"}``
         - ``content``: ``&lt;b&gt;x&lt;/b&gt;``, escaped on the way in
         - ``<span class="promo ">&lt;b&gt;x&lt;/b&gt;</span>``

    An undeclared key is dropped rather than passed through, which is the same rule from
    the other side: a shortcode receives exactly what it declared, so a stored value cannot
    smuggle in an attribute the shortcode never thought about. A missing one is not an
    error either — ``attrs.color`` falls back to ``""``, the way an omitted tag attribute
    does.

    A shortcode that declares nothing at all still renders stored values. With no
    ``content_key`` and no ``attributes``, ``"hello"``, ``{"content": "hello"}`` and
    ``{"value": "hello"}`` all arrive as the content, which is why most shortcodes need to
    do nothing here.

**What a stored value looks like.** Say the shop keeps its products in the database, one
record each, and one of the fields holds a promo code:

.. code-block:: json

    {
        "slug": "blue-mug",
        "name": "Blue mug",
        "price": "12.00",
        "promocode": {"code": "SAVE20", "color": "red"},
        "care": "Dishwasher safe"
    }

Nothing here is prose and nobody wrote a tag. What connects the record to a shortcode is
the **field name**: a field called ``promocode`` is rendered by the ``[promocode]``
shortcode, and a field no shortcode is registered under is just text. Rendering a product
is therefore a lookup per field:

.. code-block:: python

    shortcodes = app.shortcodes_for(PRODUCT_FIELD)

    def render_fields(product: dict[str, object]) -> dict[str, str]:
        rendered = {}
        for field, value in product.items():
            if shortcode := shortcodes.get(field):
                rendered[field] = shortcode.render_value(value)
            else:
                rendered[field] = escape(value)
        return rendered

.. code-block:: text

    name       -> Blue mug
    price      -> 12.00
    promocode  -> <span class="promo red">SAVE20</span>
    care       -> Dishwasher safe

The application writes this loop once, not once per shortcode: installing a plugin that
registers ``[shipping]`` makes a ``shipping`` field render, with no change here. goodmap
does exactly this for the fields shown in a map marker's popup.

Take the shortcodes from :meth:`~platzky.engine.Engine.shortcodes_for`, passing the
:term:`content type` the stored value belongs to, rather than reading ``shortcodes`` off
loaded plugins. Ask for them once and keep the result, as above: each call walks every
loaded plugin and rechecks the grant, so calling it per record pays that for nothing.

``render_value`` is called directly by the application and so does not pass through
``transform_content``, where routing is normally enforced. ``shortcodes_for`` applies the
same offer and grant that pipeline applies — the plugin's own ``accepted_content_types`` and the
site owner's ``allowed_content_types`` grant — so a site owner withholding a content type
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

