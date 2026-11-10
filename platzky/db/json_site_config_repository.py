"""SiteConfigRepository implementation backed by a shared JSON document."""

from typing_extensions import override

from platzky.db.json_document import JsonDocument, get_site_content
from platzky.db.site_config_repository import (
    LocalizedContent,
    SiteConfigRepository,
    SiteContent,
    SiteContentSection,
)


class JsonSiteConfigRepository(SiteConfigRepository):
    """Site config repository backed by a shared, in-memory document."""

    def __init__(self, document: JsonDocument) -> None:
        """Store a reference to the shared document.

        Args:
            document: The loaded document, shared with the other JSON
                repositories. Writes go through `JsonDocument.edit()`.
        """
        self._document = document

    def _section(self) -> SiteContentSection:
        """Validate and return the stored ``site_content`` section."""
        return SiteContentSection.model_validate(get_site_content(self._document.data))

    @override
    def get_site_content(self) -> SiteContent:
        """Retrieve the site-wide content.

        Returns:
            The site-wide content, with defaults where none is configured.
        """
        section = self._section()
        # Copy only the site-wide fields: the section also carries localized_content, posts, pages.
        return SiteContent(**{name: getattr(section, name) for name in SiteContent.model_fields})

    @override
    def get_localized_content(self, lang: str) -> LocalizedContent:
        """Retrieve the content of one language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The language's content, empty if none is configured for it.
        """
        return self._section().localized(lang)
