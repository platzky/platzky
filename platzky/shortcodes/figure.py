"""Built-in figure shortcode."""

from platzky.shortcodes.shortcode import Shortcode, ShortcodeAttrs

FIGURE_CSS_CLASS = "platzky-figure"


class FigureShortcode(Shortcode):
    """A picture with the text that belongs beside it."""

    name = "figure"
    description = "A picture with text beside it. Used in [slideshow] as single slide"
    example = (
        '[slideshow interval="4000"]\n'
        '  [figure][image url="/one.jpg" alt="…"]This is the first chapter.[/figure]\n'
        '  [figure][image url="/two.jpg" alt="…"]This is the second.[/figure]\n'
        "[/slideshow]"
    )
    notes = (
        'Renders a <div class="platzky-figure">. Used on its own, or as a "[slideshow]" '
        'frame — wrapped in "[figure]", an image '
        "and its caption count as a single frame; without it, each image in a "
        '"[slideshow]" is its own frame. Inside a slideshow, every frame is sized to '
        "match the first one, so keep frames similar in size."
    )

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
        """Wrap the content in a figure the stylesheet lays out.

        Args:
            attrs: Unused — a figure takes no attributes. Timing belongs to the
                ``[slideshow]`` around it, which is the thing that has a cycle.
            content: The figure's contents, already rendered. Embedded as-is per the
                ``render`` contract.

        Returns:
            The content wrapped in a ``<div>`` carrying ``FIGURE_CSS_CLASS``.
        """
        return f'<div class="{FIGURE_CSS_CLASS}">{content}</div>'


figure_shortcode = FigureShortcode()
