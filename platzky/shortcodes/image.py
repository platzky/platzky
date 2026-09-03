"""Built-in image shortcode."""

from markupsafe import escape

from platzky.shortcodes import ShortcodeAttr, ShortcodeAttrs
from platzky.shortcodes.shortcode import Shortcode
from platzky.shortcodes.urls import UrlPolicy

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
        """Render an img tag, refusing a source the policy does not permit.

        An image without a source is not an image, and ``<img src="">`` is worse than
        nothing: it draws a broken icon, and several browsers resolve the empty source
        against the current page and fetch the document a second time. The parser drops
        the whole element instead.

        Args:
            attrs: Parsed shortcode attributes (url, alt, width, height).
            content: Unused — image is a void element.

        Returns:
            An ``<img>`` tag.

        Raises:
            UrlNotPermitted: If the URL is missing, or not one the policy permits.
        """
        IMAGE_URL_POLICY.check(attrs.url)
        extra = ""
        if width := escape(attrs.width):
            extra += f' width="{width}"'
        if height := escape(attrs.height):
            extra += f' height="{height}"'
        return f'<img src="{escape(attrs.url)}" alt="{escape(attrs.alt)}"{extra}>'


image_shortcode = ImageShortcode()
