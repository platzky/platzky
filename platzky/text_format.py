"""The formats an author can write content in, and how each becomes HTML."""

import logging
from typing import Protocol

from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin

# markdown-it traces every parsing rule at DEBUG, which buries a site's own debug log.
logging.getLogger("markdown_it").setLevel(logging.INFO)


class TextFormat(Protocol):
    """How text an author wrote becomes HTML."""

    def to_html(self, text: str) -> str:
        """Turn the author's text into HTML, block structure and all.

        Args:
            text: The author's text, with a placeholder tag where each shortcode goes.

        Returns:
            The text as HTML.
        """
        ...

    def to_inline_html(self, text: str) -> str:
        """Turn the author's text into HTML without block structure.

        For text inside a shortcode element such as a link, where block structure like a
        wrapping ``<p>`` would be invalid.

        Args:
            text: The author's text, with a placeholder tag where each shortcode goes.

        Returns:
            The text as inline HTML.
        """
        ...


class _Html:
    """Text written in HTML already."""

    def to_html(self, text: str) -> str:
        """Return the text as it is."""
        return text

    def to_inline_html(self, text: str) -> str:
        """Return the text as it is."""
        return text


class _Markdown:
    """Text written in Markdown, which may mix in HTML."""

    def __init__(self) -> None:
        """Set up CommonMark with tables, strikethrough and task lists."""
        # HTML passes through: an author may mix it in, shortcode output reaches the
        # renderer as placeholder tags, and the result is sanitized afterwards.
        self._parser = (
            MarkdownIt("commonmark", {"html": True})
            .enable(["table", "strikethrough"])
            .use(tasklists_plugin)
        )

    def to_html(self, text: str) -> str:
        """Render the text from Markdown."""
        return self._parser.render(text)

    def to_inline_html(self, text: str) -> str:
        """Render the text from Markdown, inline elements only."""
        return self._parser.renderInline(text)


HTML: TextFormat = _Html()
MARKDOWN: TextFormat = _Markdown()
