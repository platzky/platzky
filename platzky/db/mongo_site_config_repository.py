"""SiteConfigRepository implementation backed by MongoDB collections."""

from collections.abc import Mapping
from functools import partial
from typing import Any

from pymongo.collection import Collection
from typing_extensions import override

from platzky.db.site_config_repository import LocalizedContent, SiteConfig, SiteConfigRepository
from platzky.db.validation import parse, validate_all


def _without_id(document: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a stored document's fields without its ``_id``, empty if there is no document."""
    return {key: value for key, value in (document or {}).items() if key != "_id"}


class MongoSiteConfigRepository(SiteConfigRepository):
    """Site config repository backed by MongoDB collections.

    The site-wide keys of `SiteConfig` are one document (``{"_id": "config", ...}``) in the
    site_config collection. The `LocalizedContent` of each language is one document
    (``{"_id": "<lang>", ...}``) in the localized_content collection.
    """

    def __init__(
        self,
        site_config: Collection[Any],
        localized_content: Collection[Any],
    ) -> None:
        """Store references to the shared collections.

        Args:
            site_config: The database's ``site_config`` collection.
            localized_content: The database's ``localized_content`` collection.
        """
        self._site_config = site_config
        self._localized_content = localized_content

    def validate(self) -> None:
        """Read the whole site config once and check it against the site config format.

        Raises:
            InvalidDataError: If the config document or a language document is invalid;
                unknown keys are reported too.
        """
        validate_all(
            (
                self.get_site_config,
                *(
                    partial(
                        parse,
                        LocalizedContent,
                        _without_id(document),
                        "localized_content",
                        str(document["_id"]),
                    )
                    for document in self._localized_content.find()
                ),
            )
        )

    @override
    def get_site_config(self) -> SiteConfig:
        """Retrieve the site-wide content.

        Returns:
            The site-wide content, with defaults where none is configured.
        """
        return parse(
            SiteConfig,
            _without_id(self._site_config.find_one({"_id": "config"})),
            "site_config",
        )

    @override
    def get_localized_content(self, lang: str) -> LocalizedContent:
        """Retrieve the content of one language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The language's content, empty if none is configured for it.
        """
        return parse(
            LocalizedContent,
            _without_id(self._localized_content.find_one({"_id": lang})),
            "localized_content",
            lang,
        )
