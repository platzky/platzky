"""SiteConfigRepository implementation backed by a shared JSON document.

It gets only the ``site_config`` section of the document: the site-wide `SiteConfig` keys and
the ``localized_content`` of each language.
"""

from typing_extensions import override

from platzky.db.json_document import JsonSection
from platzky.db.site_config_repository import LocalizedContent, SiteConfig, SiteConfigRepository
from platzky.db.validation import parse
from platzky.models import ReadOnlyMapping


class SiteConfigSection(SiteConfig):
    """The ``site_config`` section of a JSON document, as stored.

    The site-wide `SiteConfig` plus the content of each language. Unknown keys and null values
    are errors.

    Attributes:
        localized_content: The per-language content, by language code
    """

    localized_content: ReadOnlyMapping[str, LocalizedContent]


class JsonSiteConfigRepository(SiteConfigRepository):
    """Site config repository backed by a section of a shared, in-memory document."""

    def __init__(self, section: JsonSection) -> None:
        """Validate the section once: nothing changes it after the document is loaded.

        Args:
            section: The ``site_config`` section of the shared document, the only part of it
                this repository sees.

        Raises:
            InvalidDataError: If it is invalid; the message lists every problem with its
                path, one per line.
        """
        config = parse(SiteConfigSection, section, section.name)
        # Keep only the site-wide fields: the section also carries localized_content.
        self._site_config = SiteConfig(
            **{name: getattr(config, name) for name in SiteConfig.model_fields}
        )
        self._localized_content = config.localized_content

    @override
    def get_site_config(self) -> SiteConfig:
        """Retrieve the site-wide content.

        Returns:
            The site-wide content, with defaults where none is configured.
        """
        return self._site_config

    @override
    def get_localized_content(self, lang: str) -> LocalizedContent:
        """Retrieve the content of one language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The language's content, empty if none is configured for it.
        """
        return self._localized_content.get(lang, LocalizedContent())
