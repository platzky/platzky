"""Built-in code shortcode."""

from platzky.shortcodes.shortcode import Shortcode, ShortcodeAttrs


class CodeShortcode(Shortcode):
    """Show a sample without platzky reading it as syntax.

    Being ``"raw"``, nothing inside is parsed as a shortcode: ``[code][image url="…"][/code]``
    shows the tag rather than the image, which is what lets an author document a shortcode
    instead of invoking it. No text filter reaches inside either, so a plugin that rewrites
    prose cannot quietly edit a code sample.

    That is the whole of what ``"raw"`` controls — parsing. HTML written inside is not
    treated specially and behaves exactly as it would anywhere else in the content, which
    means an operator running with ``STRIP_CONTENT_HTML`` sees it removed here too. Two
    concerns, two mechanisms, and they compose without either knowing about the other.
    """

    name = "code"
    kind = "raw"
    description = "Show content as a code sample, without parsing shortcodes inside it."
    example = '[code][image url="/photo.jpg"][/code]'

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
        """Wrap the verbatim body in a preformatted code block.

        ``<pre>`` keeps the whitespace and line breaks a sample depends on, which ordinary
        HTML would collapse; ``<code>`` says what the text is.

        Args:
            attrs: Unused — code takes no attributes.
            content: Everything between the tags, exactly as written.

        Returns:
            The content wrapped in ``<pre><code>``.
        """
        return f"<pre><code>{content}</code></pre>"


code_shortcode = CodeShortcode()
