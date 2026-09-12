"""Built-in html shortcode."""

from collections.abc import Sequence

from markupsafe import Markup

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
    notes = (
        "Raw, so a shortcode tag written inside is shown literally rather than invoked — "
        "this is how to document a tag without triggering it. No text filter reaches "
        "inside either. Actual HTML written inside is rendered as HTML on the page, and "
        'stays that way even where "STRIP_CONTENT_HTML" would otherwise strip it from '
        "the rest of the post."
    )

    def render(
        self,
        attrs: ShortcodeAttrs,  # noqa: ARG002
        content: str,
        children: Sequence[Markup],  # noqa: ARG002
    ) -> str:
        """Return the body unchanged.

        Args:
            attrs: Unused — html takes no attributes.
            content: Everything between the tags, exactly as written.
            children: Unused, and always empty — a raw body is never parsed into nodes.

        Returns:
            That content, unchanged.
        """
        return content


html_shortcode = HtmlShortcode()
