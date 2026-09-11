"""Built-in slideshow shortcode."""

import logging
import re

from platzky.shortcodes import ShortcodeAttr, ShortcodeAttrs
from platzky.shortcodes.figure import FIGURE_CSS_CLASS
from platzky.shortcodes.shortcode import Shortcode

logger = logging.getLogger(__name__)

#: How long each slide is shown when the author says nothing.
DEFAULT_INTERVAL_MS = 4000

#: The floor is a safety limit rather than a matter of taste: below roughly this, a
#: cross-fade stops reading as a transition and starts reading as a flash, and WCAG's
#: three-flashes-per-second threshold is a seizure risk.
MIN_INTERVAL_MS = 1500
MAX_INTERVAL_MS = 60000

#: What ``width`` accepts. ``"fit"`` shrink-wraps to the frames, which is the only thing
#: that works for a slideshow of bare images: the first frame stays in normal flow at its
#: natural size while the rest are laid over it, so a container wider than the picture puts
#: them in different places. ``"full"`` spans whatever contains the slideshow, which is what
#: a slideshow of [figure]s usually wants, those being blocks that fill it.
WIDTHS = ("fit", "full")
DEFAULT_WIDTH = "fit"

#: How many slides the stylesheet can rotate. The animation is pure CSS, so each slide
#: count needs its own keyframe timings and `nth-child` delays written out in
#: `shortcodes.css`;
#: four is where that stops being worth the bytes. More than this is not an error — the
#: images simply render as an ordinary sequence, so nothing an author wrote disappears.
MAX_SLIDES = 4

#: Counts what the nested shortcodes produced. The parser renders and *joins* an element's
#: children before the parent ever runs, so counting markers in that string is the only way
#: a wrapper can learn how many things it wrapped — `render` receives one flat string,
#: never a list.
_IMG_RE = re.compile(r"<img\b", re.IGNORECASE)
_FIGURE_BLOCK_RE = re.compile(rf'<div class="{FIGURE_CSS_CLASS}">.*?</div>', re.DOTALL)


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
                f"Milliseconds each slide is shown (default {DEFAULT_INTERVAL_MS}, "
                f"{MIN_INTERVAL_MS}-{MAX_INTERVAL_MS})",
                required=False,
            ),
            ShortcodeAttr(
                "width",
                'Either "fit" (default, as wide as the frames) or "full" (spans its container)',
                required=False,
            ),
        ]
    )
    example = '[slideshow interval="4000"][image url="/a.jpg"][image url="/b.jpg"][/slideshow]'

    def _width(self, written: str) -> str:
        """Read the width attribute, falling back rather than failing.

        Args:
            written: The attribute exactly as the author typed it, possibly empty.

        Returns:
            One of ``WIDTHS``.
        """
        if not written:
            return DEFAULT_WIDTH
        width = written.strip().lower()
        if width not in WIDTHS:
            logger.warning(
                "[slideshow] width %r is not one of %s; using %r.",
                written,
                ", ".join(WIDTHS),
                DEFAULT_WIDTH,
            )
            return DEFAULT_WIDTH
        return width

    def _interval(self, written: str) -> int:
        """Read the interval attribute, falling back rather than failing.

        An out-of-range or non-numeric interval is corrected and logged, never raised:
        ``ShortcodeError`` is fatal by design, and a typo in one attribute should cost the
        author a warning in the log, not the whole page a 500.

        Args:
            written: The attribute exactly as the author typed it, possibly empty.

        Returns:
            A duration in milliseconds, inside the permitted range.
        """
        if not written:
            return DEFAULT_INTERVAL_MS
        try:
            interval = int(written)
        except ValueError:
            logger.warning(
                "[slideshow] interval %r is not a number; using %d.", written, DEFAULT_INTERVAL_MS
            )
            return DEFAULT_INTERVAL_MS
        clamped = max(MIN_INTERVAL_MS, min(MAX_INTERVAL_MS, interval))
        if clamped != interval:
            logger.warning(
                "[slideshow] interval %d is outside %d-%d; using %d.",
                interval,
                MIN_INTERVAL_MS,
                MAX_INTERVAL_MS,
                clamped,
            )
        return clamped

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:
        """Wrap the images in a container the stylesheet knows how to rotate.

        The slide count is written onto the element rather than inferred in CSS, because
        the timings depend on it: with N slides each is shown for one Nth of the cycle, so
        ``shortcodes.css`` carries one rule set per supported count and keys them off
        ``data-slides``. A count it has no rules for simply gets no animation, and the
        images render as an ordinary sequence.

        Args:
            attrs: Parsed attributes. Raw — escaped where interpolated.
            content: The nested shortcodes' already-rendered markup. Embedded as-is per the
                ``render`` contract; its ``Markup`` type says the escaping decision is made.

        Returns:
            A ``<div class="slideshow">`` wrapping the content.
        """
        # A [figure] is one slide regardless of how many <img> tags it holds, so its
        # block is counted once and then removed before counting bare images — otherwise
        # a slideshow mixing [figure]s with plain images would undercount.
        figure_blocks = _FIGURE_BLOCK_RE.findall(content)
        bare_content = _FIGURE_BLOCK_RE.sub("", content)
        slides = len(figure_blocks) + len(_IMG_RE.findall(bare_content))
        if slides > MAX_SLIDES:
            logger.warning(
                "[slideshow] wraps %d frames but only %d can be rotated; showing them all "
                "as a sequence instead.",
                slides,
                MAX_SLIDES,
            )
        interval = self._interval(attrs.interval)
        width = self._width(attrs.width)
        # Every interpolated value is constructed here rather than taken from the author:
        # two integers and a word from WIDTHS, so none can carry a ';' or a '"' out of the
        # attribute it lands in.
        return (
            f'<div class="slideshow" data-slides="{slides}" data-width="{width}" '
            f'style="--platzky-slideshow-interval: {interval}ms">{content}</div>'
        )


slideshow_shortcode = SlideshowShortcode()
