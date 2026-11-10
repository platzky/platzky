"""SiteConfigRepository implementation backed by a shared JSON document.

It owns the ``site_config`` section of the document: the site-wide `SiteConfig` keys and the
``localized_content`` of each language.
"""

from collections.abc import Mapping
from types import MappingProxyType

from pydantic import Field, ValidationError, field_validator
from typing_extensions import override

from platzky.db.exceptions import InvalidDataError
from platzky.db.json_document import JsonDocument, get_section
from platzky.db.site_config_repository import LocalizedContent, SiteConfig, SiteConfigRepository

SECTION = "site_config"


class SiteConfigSection(SiteConfig):
    """The ``site_config`` section of a JSON document, as stored.

    The site-wide `SiteConfig` plus the content of each language. Unknown keys and null values
    are errors.

    Attributes:
        localized_content: The per-language content, by language code
    """

    localized_content: Mapping[str, LocalizedContent] = Field(
        default_factory=lambda: MappingProxyType({})
    )

    @field_validator("localized_content", mode="after")
    @classmethod
    def _read_only(cls, value: Mapping[str, LocalizedContent]) -> Mapping[str, LocalizedContent]:
        return MappingProxyType(dict(value))


def parse_site_config(site_config: object) -> SiteConfigSection:
    """Validate the ``site_config`` section of a JSON document, e.g. when the application starts.

    Args:
        site_config: The ``site_config`` section of the document.

    Returns:
        The validated section.

    Raises:
        InvalidDataError: If it is invalid; the message lists every problem with its
            path, one per line.
    """
    try:
        return SiteConfigSection.model_validate(site_config)
    except ValidationError as error:
        raise InvalidDataError.from_validation_error(error, SECTION) from error


class JsonSiteConfigRepository(SiteConfigRepository):
    """Site config repository backed by a shared, in-memory document."""

    def __init__(self, document: JsonDocument) -> None:
        """Store a reference to the shared document.

        Args:
            document: The loaded document, shared with the other JSON
                repositories. Writes go through `JsonDocument.edit()`.
        """
        self._document = document

    def _section(self) -> SiteConfigSection:
        """Validate and return the stored ``site_config`` section."""
        return parse_site_config(get_section(self._document.data, SECTION))

    @override
    def get_site_config(self) -> SiteConfig:
        """Retrieve the site-wide content.

        Returns:
            The site-wide content, with defaults where none is configured.
        """
        section = self._section()
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
        return self._section().localized_content.get(lang, LocalizedContent())
