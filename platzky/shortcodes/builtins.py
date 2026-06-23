"""Built-in shortcode handlers for images and links."""

from platzky.shortcodes import Shortcode
from platzky.shortcodes.hero import hero_shortcode
from platzky.shortcodes.image import image_shortcode
from platzky.shortcodes.link import link_shortcode


def get_builtin_shortcodes() -> dict[str, Shortcode]:
    """Return built-in shortcode descriptors for images, links, and hero blocks.

    Returns:
        Map of tag name to Shortcode for the built-in image, link, and hero tags.
    """
    return {
        image_shortcode.name: image_shortcode,
        link_shortcode.name: link_shortcode,
        hero_shortcode.name: hero_shortcode,
    }
