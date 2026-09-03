"""Built-in image shortcode."""

import logging

from markupsafe import escape

from platzky.shortcodes import ShortcodeAttr, ShortcodeAttrs
from platzky.shortcodes.shortcode import Shortcode
from platzky.shortcodes.urls import UrlPolicy

logger = logging.getLogger(__name__)

#: An image source has to be something the browser can download, so this policy permits only
#: ``http`` and ``https``. ``mailto:`` and ``tel:`` hand off to another application instead,
#: which makes them fine in a link but useless as an image source.
#:
#: It lives here and is not exported because this shortcode is its only consumer, unlike
#: ``LINK_URL_POLICY``, which goodmap needs too.
IMAGE_URL_POLICY = UrlPolicy(frozenset({"http", "https"}))


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
        if fault := IMAGE_URL_POLICY.fault(attrs.url):
            logger.warning(
                "[image] rendered nothing: %s; use %s.", fault.value, IMAGE_URL_POLICY.permits()
            )
            return ""
        extra = ""
        if width := escape(attrs.width):
            extra += f' width="{width}"'
        if height := escape(attrs.height):
            extra += f' height="{height}"'
        return f'<img src="{escape(attrs.url)}" alt="{escape(attrs.alt)}"{extra}>'


image_shortcode = ImageShortcode()
