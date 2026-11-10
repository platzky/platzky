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
        """Store the section.

        Args:
            section: The ``site_config`` section of the shared document, the only part of it
                this repository sees.
        """
        self._section = section

    def _parsed(self) -> SiteConfigSection:
        """Validate and return the stored section."""
        return parse(SiteConfigSection, self._section, self._section.name)

    def validate(self) -> None:
        """Check the section against the site config format, e.g. when the application starts.

        Raises:
            InvalidDataError: If it is invalid; the message lists every problem with its
                path, one per line.
        """
        self._parsed()

    @override
    def get_site_config(self) -> SiteConfig:
        """Retrieve the site-wide content.

        Returns:
            The site-wide content, with defaults where none is configured.
        """
        section = self._parsed()
        # Copy only the site-wide fields: the section also carries localized_content.
        return SiteConfig(**{name: getattr(section, name) for name in SiteConfig.model_fields})

    @override
    def get_localized_content(self, lang: str) -> LocalizedContent:
        """Retrieve the content of one language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The language's content, empty if none is configured for it.
        """
        return self._parsed().localized_content.get(lang, LocalizedContent())
