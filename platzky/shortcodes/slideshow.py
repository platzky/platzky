"""Built-in slideshow shortcode."""

import logging

from platzky.shortcodes import IntRange, OneOf, ShortcodeAttr, ShortcodeAttrs
from platzky.shortcodes.shortcode import Content, OnlyChildren, Shortcode

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_MS = 4000
# Our min interval is, deliberately higher than anything the standards ask for.
# WCAG sets no minimum interval at all, but the nearest number is in 2.3.1 Three Flashes
# or Below Threshold (https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html):
#
#     "Web pages do not contain anything that flashes more than three times in any one
#      second period, or the flash is below the general flash and red flash thresholds."
#
MIN_INTERVAL_MS = 500
MAX_INTERVAL_MS = 60000

DEFAULT_WIDTH = "fit"

DEFAULT_ANIMATION = "crossfade"

# Not a free setting: shortcodes.css has one hand-written rule set per slide count (2-4).
# Raising this without adding the matching CSS leaves larger slideshows unanimated, unlogged.
MAX_SLIDES = 4


class SlideshowShortcode(Shortcode):
    """Rotate between the frames it wraps, on a timer."""

    name = "slideshow"
    description = "Rotate between the [figure]s inside it. Rotates up to four."
    attributes = ShortcodeAttrs(
        [
            ShortcodeAttr(
                "interval",
                "Milliseconds each slide is shown.",
                default=str(DEFAULT_INTERVAL_MS),
                constraints=IntRange(MIN_INTERVAL_MS, MAX_INTERVAL_MS),
            ),
            ShortcodeAttr(
                "width",
                '"fit" is as wide as the frames; "full" spans its container.',
                default=DEFAULT_WIDTH,
                constraints=OneOf("fit", "full"),
            ),
            ShortcodeAttr(
                "animation",
                '"crossfade" dissolves one frame into the next; "fade" fades each out before '
                'the next fades in, so captions never overlap; "cut" switches instantly.',
                default=DEFAULT_ANIMATION,
                constraints=OneOf("crossfade", "fade", "cut"),
            ),
        ]
    )
    child_policy = OnlyChildren(frozenset({"figure"}))
    example = (
        '[slideshow interval="4000"]\n'
        '  [figure image="/a.jpg"]The first slide.[/figure]\n'
        '  [figure image="/b.jpg"]The second.[/figure]\n'
        "[/slideshow]"
    )
    notes = (
        'Every frame is a "[figure]", one slide each; a slideshow holding anything else, '
        "a stray word included, renders nothing and says so in the log. Up to four frames "
        "rotate, more render as an ordinary sequence instead. The rotation is pure CSS and "
        'pauses on hover or focus; with "prefers-reduced-motion: reduce", slides still '
        "rotate but switch instantly, whichever animation is set."
    )

    def render(self, attrs: ShortcodeAttrs, content: Content) -> str:
        """Wrap the frames in a container the stylesheet knows how to rotate.

        The slide count is written onto the element rather than inferred in CSS, because
        the timings depend on it: with N slides each is shown for one Nth of the cycle, so
        ``shortcodes.css`` carries one rule set per supported count and keys them off
        ``data-slides``. A count it has no rules for simply gets no animation, and the
        frames render as an ordinary sequence.

        Args:
            attrs: Parsed attributes; ``interval``, ``width`` and ``animation`` already
                checked against their ``constraints``.
            content: The frames' already-rendered markup. Embedded as-is per the ``render``
                contract; its ``Markup`` type says the escaping decision is made. Its
                ``elements`` hold one entry per frame, so a ``[figure]`` counts once however
                much markup it holds.

        Returns:
            A ``<div class="slideshow">`` wrapping the content.
        """
        # A stored value arrives with no elements, since nobody wrote tags to nest: its
        # content is the single frame.
        slides = len(content.elements) if content.elements else (1 if content else 0)
        if slides > MAX_SLIDES:
            logger.warning(
                "[slideshow] wraps %d frames but only %d can be rotated; showing them all "
                "as a sequence instead.",
                slides,
                MAX_SLIDES,
            )
        # slides is a length, and interval, width and animation only got past their
        # constraints as bare digits and known words, so none can carry a ';' or a '"' out
        # of the attribute it lands in.
        return (
            f'<div class="slideshow" data-slides="{slides}" data-width="{attrs.width}" '
            f'data-animation="{attrs.animation}" '
            f'style="--platzky-slideshow-interval: {attrs.interval}ms">{content}</div>'
        )


slideshow_shortcode = SlideshowShortcode()
