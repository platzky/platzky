"""SiteConfigRepository implementation backed by MongoDB collections."""

from collections.abc import Mapping
from typing import Any

from pymongo.collection import Collection
from typing_extensions import override

from platzky.db.site_config_repository import (
    LocalizedContent,
    SiteConfigRepository,
    SiteContent,
    parse_site_content,
)


def _without_id(document: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a stored document's fields without its ``_id``, empty if there is no document."""
    return {key: value for key, value in (document or {}).items() if key != "_id"}


class MongoSiteConfigRepository(SiteConfigRepository):
    """Site config repository backed by MongoDB collections.

    The site-wide keys of `SiteContent` are one document (``{"_id": "config", ...}``) in the
    site_content collection. The `LocalizedContent` of each language is one document
    (``{"_id": "<lang>", ...}``) in the localized_content collection.
    """

    def __init__(
        self,
        site_content: Collection[Any],
        localized_content: Collection[Any],
    ) -> None:
        """Store references to the shared collections.

        Args:
            site_content: The database's ``site_content`` collection.
            localized_content: The database's ``localized_content`` collection.
        """
        self._site_content = site_content
        self._localized_content = localized_content

    def validate(self) -> None:
        """Read the whole site content once and check it against the site content format.

        Raises:
            InvalidSiteContentError: If the config document or a language document is invalid;
                unknown keys are reported too.
        """
        parse_site_content(
            {
                **_without_id(self._site_content.find_one({"_id": "config"})),
                "localized_content": {
                    document["_id"]: _without_id(document)
                    for document in self._localized_content.find()
                },
            }
        )

    @override
    def get_site_content(self) -> SiteContent:
        """Retrieve the site-wide content.

        Returns:
            The site-wide content, with defaults where none is configured.
        """
        return SiteContent.model_validate(
            _without_id(self._site_content.find_one({"_id": "config"}))
        )

    @override
    def get_localized_content(self, lang: str) -> LocalizedContent:
        """Retrieve the content of one language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The language's content, empty if none is configured for it.
        """
        return LocalizedContent.model_validate(
            _without_id(self._localized_content.find_one({"_id": lang}))
        )
