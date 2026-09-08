"""Built-in slide shortcode."""

from platzky.shortcodes.shortcode import Shortcode, ShortcodeAttrs

#: The class the stylesheet lays out, and the marker ``[slideshow]`` counts to learn how
#: many slides it wraps. It is only ever selected as a child of ``.slideshow``, so a site
#: that uses ``slide`` for something of its own is unaffected.
SLIDE_CLASS = "slide"


class SlideShortcode(Shortcode):
    """One frame of a ``[slideshow]``, holding whatever an author puts in it."""

    name = "slide"
    description = (
        "One frame of a [slideshow]. Wrap an image and its text together to show them "
        "side by side; without it, each image is a frame on its own."
    )
    example = '[slide][image url="/a.jpg"]The first chapter.[/slide]'

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
        """Wrap the content in a frame the slideshow stylesheet lays out.

        Args:
            attrs: Unused — a slide takes no attributes; the timing belongs to the
                slideshow around it, which is the thing that has a cycle.
            content: The frame's contents, already rendered. Embedded as-is per the
                ``render`` contract.

        Returns:
            The content wrapped in a ``<div class="slide">``.
        """
        return f'<div class="{SLIDE_CLASS}">{content}</div>'


slide_shortcode = SlideShortcode()
