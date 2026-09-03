"""Built-in image shortcode."""

import logging

from markupsafe import escape

from platzky.shortcodes import ShortcodeAttr, ShortcodeAttrs
from platzky.shortcodes.shortcode import Shortcode
from platzky.shortcodes.urls import UrlPolicy

logger = logging.getLogger(__name__)

#: Only the two schemes that fetch a document over the network: an ``<img src="mailto:…">``
#: is not an image.
#:
#: Lives here rather than beside ``LINK_URL_POLICY`` in :mod:`platzky.shortcodes.urls`, and is
#: not re-exported from :mod:`platzky.shortcodes`, because this shortcode is its only consumer.
#: ``LINK_URL_POLICY`` is exported because it has a second one: an application rendering a
#: ``hyperlink`` value of its own (see goodmap) has to agree with ``[link]`` about what may be
#: linked to. Export this the day something has the same need of an image's policy.
EMBED_URL_POLICY = UrlPolicy(frozenset({"http", "https"}))


class ImageShortcode(Shortcode):
    """Render an ``<img>`` tag from shortcode attributes."""

    name = "image"
    description = "Embed an image."
    attributes = ShortcodeAttrs(
        [
            ShortcodeAttr("url", "Image URL (http/https or a path starting with /)", required=True),
            ShortcodeAttr("alt", "Alt text", required=False),
            ShortcodeAttr("width", "Width in pixels", required=False),
            ShortcodeAttr("height", "Height in pixels", required=False),
        ]
    )
    example = '[image url="https://example.com/photo.jpg" alt="A photo"]'
    kind = "void"

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
        """Render an img tag, or nothing at all when there is no usable source.

        An image without a source is not an image, and ``<img src="">`` is worse than
        nothing: it draws a broken icon, and several browsers resolve the empty source
        against the current page and fetch the document a second time. So the tag renders
        to nothing — and logs, because an author cannot see an absence.

        Args:
            attrs: Parsed shortcode attributes (url, alt, width, height).
            content: Unused — image is a void element.

        Returns:
            An ``<img>`` tag, or empty string if the URL is missing or not allowed.
        """
        if not EMBED_URL_POLICY.allows(attrs.url):
            logger.warning(
                "[image] rendered nothing: %s.", EMBED_URL_POLICY.rejection_reason(attrs.url)
            )
            return ""
        extra = ""
        if width := escape(attrs.width):
            extra += f' width="{width}"'
        if height := escape(attrs.height):
            extra += f' height="{height}"'
        return f'<img src="{escape(attrs.url)}" alt="{escape(attrs.alt)}"{extra}>'


image_shortcode = ImageShortcode()
