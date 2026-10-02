"""Built-in figure shortcode."""

from markupsafe import escape

from platzky.shortcodes import IntRange, ShortcodeAttr, ShortcodeAttrs
from platzky.shortcodes.shortcode import Content, Shortcode
from platzky.shortcodes.urls import IMAGE_URL_POLICY

FIGURE_CSS_CLASS = "platzky-figure"
FIGURE_CAPTION_CSS_CLASS = "platzky-figure-caption"


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
        'Renders a <div class="platzky-figure">, with the caption in its own '
        '<div class="platzky-figure-caption">. Used on its own, or as a "[slideshow]" '
        'frame — a "[figure]" is always a single slide, however much it holds, and is the '
        'only thing a "[slideshow]" accepts. A slideshow is as large as its largest frame, '
        "so keep frames similar in size to avoid empty space around the smaller ones."
    )

    def render(self, attrs: ShortcodeAttrs, content: Content) -> str:
        """Wrap an image and its caption in a figure the stylesheet lays out.

        The caption gets a box of its own so a stylesheet can place it beside the picture as
        one item — with flex, say — without splitting a sentence at every link or span in it.

        Args:
            attrs: Parsed shortcode attributes (image, alt, width, height).
            content: The caption, already rendered. Embedded as-is per the ``render``
                contract.

        Returns:
            The image, and the caption in a ``<div>`` carrying ``FIGURE_CAPTION_CSS_CLASS``
            when there is one, wrapped in a ``<div>`` carrying ``FIGURE_CSS_CLASS``.

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
        caption = f'<div class="{FIGURE_CAPTION_CSS_CLASS}">{content}</div>' if content else ""
        return f'<div class="{FIGURE_CSS_CLASS}">{img}{caption}</div>'


figure_shortcode = FigureShortcode()
