"""Built-in shortcode handlers for images, links, hero blocks and code samples."""

from platzky.shortcodes import Shortcode
from platzky.shortcodes.code import code_shortcode
from platzky.shortcodes.hero import hero_shortcode
from platzky.shortcodes.image import image_shortcode
from platzky.shortcodes.link import link_shortcode


def get_builtin_shortcodes() -> dict[str, Shortcode]:
    """Return built-in shortcode descriptors.

    Returns:
        Map of tag name to Shortcode for the built-in image, link, hero and code tags.
    """
    return {
        image_shortcode.name: image_shortcode,
        link_shortcode.name: link_shortcode,
        hero_shortcode.name: hero_shortcode,
        code_shortcode.name: code_shortcode,
    }
