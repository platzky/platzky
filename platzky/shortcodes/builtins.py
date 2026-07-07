"""Built-in shortcode handlers for images and links."""

from platzky.shortcodes import Shortcode
from platzky.shortcodes.image import image_shortcode
from platzky.shortcodes.link import link_shortcode


def get_builtin_shortcodes() -> dict[str, Shortcode]:
    """Return built-in shortcode descriptors for images and links.

    Returns:
        Map of tag name to Shortcode for the built-in image and link tags.
    """
    return {
        image_shortcode.name: image_shortcode,
        link_shortcode.name: link_shortcode,
    }
