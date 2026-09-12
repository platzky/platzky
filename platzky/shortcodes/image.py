"""Built-in image shortcode."""

from collections.abc import Sequence

from markupsafe import Markup, escape

from platzky.shortcodes import IntRange, ShortcodeAttr, ShortcodeAttrs
from platzky.shortcodes.shortcode import Shortcode
from platzky.shortcodes.urls import IMAGE_URL_POLICY


class ImageShortcode(Shortcode):
    """Render an ``<img>`` tag from shortcode attributes."""

    name = "image"
    description = "Embed an image."
    attributes = ShortcodeAttrs(
        [
            ShortcodeAttr("url", "Image URL (http/https or a path starting with /)", required=True),
            ShortcodeAttr("alt", "Alt text", required=False),
            ShortcodeAttr("width", "Width in pixels", constraints=IntRange(1)),
            ShortcodeAttr("height", "Height in pixels", constraints=IntRange(1)),
        ]
    )
    example = '[image url="https://example.com/photo.jpg" alt="A photo"]'
    kind = "void"

    def render(
        self,
        attrs: ShortcodeAttrs,
        content: str,  # noqa: ARG002
        children: Sequence[Markup],  # noqa: ARG002
    ) -> str:
        """Render an img tag, refusing a source the policy does not permit.

        An image without a source is not an image, and ``<img src="">`` is worse than
        nothing: it draws a broken icon, and several browsers resolve the empty source
        against the current page and fetch the document a second time. The parser drops
        the whole element instead.

        Args:
            attrs: Parsed shortcode attributes (url, alt, width, height).
            content: Unused — image is a void element.
            children: Unused, and always empty — a void element wraps nothing.

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
