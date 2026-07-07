"""Built-in hero shortcode."""

from platzky.shortcodes.shortcode import Shortcode, ShortcodeAttrs


class HeroShortcode(Shortcode):
    """Wrap content in a header block, independent of the page/post masthead."""

    name = "hero"
    description = "Wrap content in a hero/header block, anywhere in the body."
    example = "[hero]<h1>Headline</h1><p>Subheading text</p>[/hero]"

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
        """Wrap the inner content in a ``.hero`` container, used as-is.

        Args:
            attrs: Unused — hero currently takes no attributes.
            content: Raw inner HTML/text between the tags.

        Returns:
            The content wrapped in a ``<div class="hero">``.
        """
        return f'<div class="hero">{content}</div>'


hero_shortcode = HeroShortcode()
