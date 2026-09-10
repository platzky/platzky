"""Built-in shortcode handlers for images, links, hero blocks, verbatim HTML and slideshows."""

from platzky.shortcodes import Shortcode
from platzky.shortcodes.figure import figure_shortcode
from platzky.shortcodes.hero import hero_shortcode
from platzky.shortcodes.html import html_shortcode
from platzky.shortcodes.image import image_shortcode
from platzky.shortcodes.link import link_shortcode
from platzky.shortcodes.slideshow import slideshow_shortcode


def get_builtin_shortcodes() -> dict[str, Shortcode]:
    """Return built-in shortcode descriptors.

    Returns:
        Map of tag name to Shortcode for the built-in image, link, hero, html and
        slideshow tags, and the figure frames a slideshow holds.
    """
    return {
        image_shortcode.name: image_shortcode,
        link_shortcode.name: link_shortcode,
        hero_shortcode.name: hero_shortcode,
        html_shortcode.name: html_shortcode,
        figure_shortcode.name: figure_shortcode,
        slideshow_shortcode.name: slideshow_shortcode,
    }
