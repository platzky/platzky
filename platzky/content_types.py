"""Content types — the kinds of content platzky can hand to a transformer plugin.

Platzky produces the three below. An application or a plugin large enough to bring its
own kind of content — a map marker's fields, a catalogue's attributes — names its own and
registers it, so nothing has to be built around it.

The vocabulary is therefore open, and a content type is just its name: a plugin accepting
a kind of content another package brought never has to import that package, and installs
just as cleanly where no such content exists, being simply never called.

That openness costs static checking, which a closed ``Literal`` would give but cannot
survive extension — platzky cannot know at type-check time what a package it has never
heard of will add. A package that *does* know its own whole vocabulary can narrow for its
own code::

    GoodmapContentType = Literal["post", "page", "comment", "field"]

which type-checks its own call sites while the boundary here stays open.
"""

ContentType = str

POST: ContentType = "post"
PAGE: ContentType = "page"
COMMENT: ContentType = "comment"

#: The content types platzky itself hands to transformers.
BUILTIN_CONTENT_TYPES: frozenset[ContentType] = frozenset({POST, PAGE, COMMENT})


class _AllContentTypes(str):
    """Sentinel key type for ``ALL_CONTENT_TYPES``; identity-checked, never matched by name."""


#: Use as the key in ``accepted_content_types`` when a plugin has no technical constraint
#: on where it runs — a shortcode that merely wraps whatever it is given, and would work
#: as well on a catalogue attribute as on a post::
#:
#:     accepted_content_types = {ALL_CONTENT_TYPES: "Wherever you want codes revealed."}
#:
#: It resolves against the vocabulary the application actually has, so a plugin written
#: today is offered a content type invented tomorrow and never hardcodes a name belonging
#: to a package it does not depend on. Resolution is lazy: plugins contribute types as
#: they load, so the answer is only complete once loading is done.
#:
#: It is not a way to skip the question, and it grants nothing. An operator still names
#: every content type they want the plugin to act on, and silence is still refusal — the
#: wildcard only decides which types they are *offered*. A plugin whose shortcode embeds
#: raw markup, reaches an external host, or costs something to run has a real constraint
#: and should enumerate instead.
ALL_CONTENT_TYPES: ContentType = _AllContentTypes("*")
