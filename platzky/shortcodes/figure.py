"""Built-in figure shortcode."""

from collections.abc import Sequence

from markupsafe import Markup, escape

from platzky.shortcodes import IntRange, ShortcodeAttr, ShortcodeAttrs
from platzky.shortcodes.shortcode import Shortcode
from platzky.shortcodes.urls import IMAGE_URL_POLICY

FIGURE_CSS_CLASS = "platzky-figure"


class FigureShortcode(Shortcode):
    """A picture with the text that belongs beside it."""

    name = "figure"
    description = "A picture with text beside it. Used in [slideshow] as single slide"
    attributes = ShortcodeAttrs(
        [
            ShortcodeAttr(
                "image", "Image URL (http/https or a path starting with /)", required=True
            ),
            ShortcodeAttr("alt", "Alt text", required=False),
            ShortcodeAttr("width", "Width in pixels", constraints=IntRange(1)),
            ShortcodeAttr("height", "Height in pixels", constraints=IntRange(1)),
        ]
    )
    example = (
        '[slideshow interval="4000"]\n'
        '  [figure image="/one.jpg" alt="…"]This is the first chapter.[/figure]\n'
        '  [figure image="/two.jpg" alt="…"]This is the second.[/figure]\n'
        "[/slideshow]"
    )
    notes = (
        'Renders a <div class="platzky-figure">. Used on its own, or as a "[slideshow]" '
        'frame — a "[figure]" is always a single slide, however it is used. Without it, '
        'each bare image in a "[slideshow]" is its own frame. Inside a slideshow, every '
        "frame is sized to match the first one, so keep frames similar in size."
    )

    def render(
        self,
        attrs: ShortcodeAttrs,
        content: str,
        children: Sequence[Markup],  # noqa: ARG002
    ) -> str:
        """Wrap an image and its caption in a figure the stylesheet lays out.

        Args:
            attrs: Parsed shortcode attributes (image, alt, width, height).
            content: The caption, already rendered. Embedded as-is per the ``render``
                contract.
            children: Unused — the layout does not depend on what the caption wrapped.

        Returns:
            The image and caption wrapped in a ``<div>`` carrying ``FIGURE_CSS_CLASS``.

        Raises:
            UrlNotPermitted: If the image URL is missing, or not one the policy permits.
        """
        IMAGE_URL_POLICY.check(attrs.image)
        extra = ""
        if width := escape(attrs.width):
            extra += f' width="{width}"'
        if height := escape(attrs.height):
            extra += f' height="{height}"'
        img = f'<img src="{escape(attrs.image)}" alt="{escape(attrs.alt)}"{extra}>'
        return f'<div class="{FIGURE_CSS_CLASS}">{img}{content}</div>'


figure_shortcode = FigureShortcode()
