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
