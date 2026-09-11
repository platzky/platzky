"""Built-in figure shortcode."""

from platzky.shortcodes.shortcode import Shortcode, ShortcodeAttrs

FIGURE_CSS_CLASS = "platzky-figure"

class FigureShortcode(Shortcode):
    """A picture with the text that belongs beside it."""

    name = "figure"
    description = (
        "A picture with text beside it. Used in [slideshow] as single slide"
    )
    example = '[figure][image url="/a.jpg"]The first chapter.[/figure]'

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
