"""Built-in slideshow shortcode."""

import logging
from collections.abc import Sequence

from markupsafe import Markup

from platzky.shortcodes import IntRange, OneOf, ShortcodeAttr, ShortcodeAttrs
from platzky.shortcodes.shortcode import Shortcode

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_MS = 4000
MIN_INTERVAL_MS = 1500  # seizure-safety floor (WCAG 2.3.1: at most three flashes a second)
MAX_INTERVAL_MS = 60000

DEFAULT_WIDTH = "fit"

# Not a free setting: shortcodes.css has one hand-written rule set per slide count (2-4).
# Raising this without adding the matching CSS leaves larger slideshows unanimated, unlogged.
MAX_SLIDES = 4


class SlideshowShortcode(Shortcode):
    """Cross-fade between the frames it wraps, on a timer, using no JavaScript."""

    name = "slideshow"
    description = (
        "Cross-fade between the [figure]s inside it, or between bare images. Rotates up to four."
    )
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
        ]
    )
    example = '[slideshow interval="4000"][image url="/a.jpg"][image url="/b.jpg"][/slideshow]'
    notes = (
        'Each frame is a bare image or a "[figure]"; up to four frames rotate, more render '
        "as an ordinary sequence instead. The rotation is pure CSS and pauses on hover or "
        'focus; with "prefers-reduced-motion: reduce", slides still rotate but without the '
        "cross-fade."
    )

    def render(self, attrs: ShortcodeAttrs, content: Markup, children: Sequence[Markup]) -> str:
        """Wrap the frames in a container the stylesheet knows how to rotate.

        The slide count is written onto the element rather than inferred in CSS, because
        the timings depend on it: with N slides each is shown for one Nth of the cycle, so
        ``shortcodes.css`` carries one rule set per supported count and keys them off
        ``data-slides``. A count it has no rules for simply gets no animation, and the
        frames render as an ordinary sequence.

        Args:
            attrs: Parsed attributes; ``interval`` and ``width`` already checked against
                their ``constraints``.
            content: The frames' already-rendered markup. Embedded as-is per the ``render``
                contract; its ``Markup`` type says the escaping decision is made.
            children: One entry per frame, so a ``[figure]`` counts once however much
                markup it holds.

        Returns:
            A ``<div class="slideshow">`` wrapping the content.
        """
        # A stored value arrives with no children, since nobody wrote tags to nest: its
        # content is the single frame.
        slides = len(children) if children else (1 if content else 0)
        if slides > MAX_SLIDES:
            logger.warning(
                "[slideshow] wraps %d frames but only %d can be rotated; showing them all "
                "as a sequence instead.",
                slides,
                MAX_SLIDES,
            )
        # slides is a length, and interval and width only got past their constraints as
        # bare digits and a known word, so none can carry a ';' or a '"' out of the
        # attribute it lands in.
        return (
            f'<div class="slideshow" data-slides="{slides}" data-width="{attrs.width}" '
            f'style="--platzky-slideshow-interval: {attrs.interval}ms">{content}</div>'
        )


slideshow_shortcode = SlideshowShortcode()
