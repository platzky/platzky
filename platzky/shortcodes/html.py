"""Built-in html shortcode."""

from platzky.shortcodes.shortcode import Shortcode, ShortcodeAttrs


class HtmlShortcode(Shortcode):
    """Pass content through exactly as written.

    Being ``"raw"``, nothing inside is parsed as a shortcode: ``[html][image url="…"][/html]``
    shows the tag rather than the image, which is what lets an author document a shortcode
    instead of invoking it. No text filter reaches inside either, so a plugin that rewrites
    prose cannot quietly edit what is in here.

    Verbatim also means HTML written inside reaches the page as HTML, and keeps doing so
    where ``STRIP_CONTENT_HTML`` removes the HTML around it: the flag has the site owner
    decide that prose is not written in HTML, and this tag is how an author says a
    particular piece of it is meant. That escape hatch is only open to whoever the caller
    vouched for — an author with CMS write access. Content nobody vouched for, a comment
    say, is escaped at the boundary before any of this runs, raw bodies with it, so a
    stranger writing ``[html]`` gets the characters shown back rather than a way in.
    """

    name = "html"
    kind = "raw"
    description = "Emit content exactly as written, parsing neither shortcodes nor HTML in it."
    example = '[html]<img src="/photo.jpg">[/html]'

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
        """Return the body unchanged.

        Args:
            attrs: Unused — html takes no attributes.
            content: Everything between the tags, exactly as written.

        Returns:
            That content, unchanged.
        """
        return content


html_shortcode = HtmlShortcode()
