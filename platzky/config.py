"""Configuration module for Platzky application.

This module defines all configuration models and parsing logic for the application.
"""

import re
import sys
import typing as t
from functools import cached_property

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.config import ExtraValues

from platzky.attachment.constants import BLOCKED_EXTENSIONS, DEFAULT_MAX_ATTACHMENT_SIZE
from platzky.db.db import DBConfig
from platzky.db.db_loader import get_db_module
from platzky.feature_flags_wrapper import FeatureFlagSet
from platzky.language_routing import RESERVED_PATH_SEGMENTS, SiteLanguages
from platzky.telemetry import TelemetryConfig


class LanguageConfig(BaseModel):
    """Configuration for a single language.

    Attributes:
        name: Display name of the language
        flag: Flag icon code (country code)
        country: Country code
        domain: Optional domain specific to this language
    """

    model_config = ConfigDict(frozen=True)

    name: str
    flag: str
    country: str
    domain: t.Optional[str] = None

    @field_validator("domain")
    @classmethod
    def validate_domain_is_lowercase(cls, domain: t.Optional[str]) -> t.Optional[str]:
        """Reject a domain with capitals, which would never match: browsers lowercase hosts."""
        if domain is not None and domain != domain.lower():
            raise ValueError(
                f"domain {domain!r} must be lowercase ({domain.lower()!r}); browsers send the "
                "host in lowercase, so it would never match."
            )
        return domain


Languages = dict[str, LanguageConfig]
LanguagesMapping = t.Mapping[str, t.Mapping[str, str]]

_PATH_SEGMENT = re.compile(r"[A-Za-z0-9_-]+")
LogLevel = t.Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]


def languages_dict(languages: Languages) -> LanguagesMapping:
    """Convert Languages configuration to a mapping dictionary.

    Excludes None values to align with type signature.

    Args:
        languages: Dictionary of language configurations

    Returns:
        Mapping of language codes to their configuration dictionaries (excludes None values)
    """
    return {
        name: {k: v for k, v in lang.model_dump().items() if v is not None}
        for name, lang in languages.items()
    }


_DEFAULT_ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        # Image types (binary formats with verifiable magic bytes)
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/bmp",
        "image/tiff",
        # Application types (binary formats)
        "application/pdf",
        # Archive types - validated but NEVER auto-extracted (zip bomb protection)
        "application/zip",
        "application/gzip",
        "application/x-tar",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        # Audio types
        "audio/mpeg",
        "audio/wav",
        "audio/ogg",
        # Video types
        "video/mp4",
        "video/webm",
        "video/ogg",
        # Note: Text types (text/*, application/json, application/xml, application/rtf,
        # image/svg+xml) are NOT included by default for security reasons. They can
        # bypass content validation and may contain executable code. To allow text
        # types, explicitly add them:
        #   AttachmentConfig(allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"})
    }
)


class AttachmentConfig(BaseModel):
    """Configuration for attachment handling.

    Attributes:
        allowed_mime_types: MIME types allowed for attachments.
        validate_content: Whether to validate content matches declared MIME type.
        allow_unrecognized_content: If True, allow content that cannot be identified.
        max_size: Maximum attachment size in bytes (default: 10MB).
        blocked_extensions: File extensions that are PERMANENTLY blocked (executable
            and script formats). These cannot be overridden via allowed_extensions.
        allowed_extensions: File extensions to allow. Defaults to common safe formats
            (images, documents, archives, audio/video). Set to None to block all.
            Note: blocked_extensions takes precedence over allowed_extensions.
            Files without extensions are always blocked when allowed_extensions is set.
    """

    model_config = ConfigDict(frozen=True)

    allowed_mime_types: frozenset[str] = Field(default=_DEFAULT_ALLOWED_MIME_TYPES)
    validate_content: bool = Field(default=True)
    allow_unrecognized_content: bool = Field(default=False)
    max_size: int = Field(default=DEFAULT_MAX_ATTACHMENT_SIZE, gt=0)
    blocked_extensions: frozenset[str] = Field(default=BLOCKED_EXTENSIONS)
    allowed_extensions: frozenset[str] | None = Field(
        default=frozenset(
            {
                # Images
                "png",
                "jpg",
                "jpeg",
                "gif",
                "webp",
                "bmp",
                "tiff",
                # Documents
                "pdf",
                "doc",
                "docx",
                "xls",
                "xlsx",
                "ppt",
                "pptx",
                # Archives
                "zip",
                "gz",
                "tar",
                # Audio/Video
                "mp3",
                "wav",
                "ogg",
                "mp4",
                "webm",
            }
        )
    )


class Config(BaseModel):
    """Main application configuration.

    Attributes:
        app_name: Application name
        secret_key: Flask secret key for sessions
        db: Database configuration
        use_www: Redirect non-www to www URLs
        seo_prefix: URL prefix for SEO routes
        blog_prefix: URL prefix for blog routes
        languages: Supported languages configuration
        default_language: Language served at the root of the main host
        translation_directories: Additional translation directories
        log_level: Level of the application's logs; defaults to INFO, development to DEBUG
        testing: Enable testing mode
        feature_flags: Feature flag configuration
        telemetry: OpenTelemetry configuration
        attachment: Attachment handling configuration
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    app_name: str = Field(alias="APP_NAME")
    secret_key: str = Field(alias="SECRET_KEY")
    db: DBConfig = Field(alias="DB")
    use_www: bool = Field(default=True, alias="USE_WWW")
    seo_prefix: str = Field(default="/", alias="SEO_PREFIX")
    blog_prefix: str = Field(default="/blog", alias="BLOG_PREFIX")
    languages: Languages = Field(default_factory=dict, alias="LANGUAGES")
    default_language: str = Field(alias="DEFAULT_LANGUAGE")
    translation_directories: list[str] = Field(
        default_factory=list,
        alias="TRANSLATION_DIRECTORIES",
    )
    log_level: t.Optional[LogLevel] = Field(default=None, alias="LOG_LEVEL")
    testing: bool = Field(default=False, alias="TESTING")
    feature_flags: FeatureFlagSet = Field(
        default_factory=lambda: FeatureFlagSet({}),
        alias="FEATURE_FLAGS",
    )
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig, alias="TELEMETRY")
    attachment: AttachmentConfig = Field(default_factory=AttachmentConfig, alias="ATTACHMENT")
    sitemap_excluded_prefixes: list[str] = Field(
        default_factory=list,
        alias="SITEMAP_EXCLUDED_PREFIXES",
    )

    @field_validator("blog_prefix")
    @classmethod
    def validate_blog_prefix(cls, prefix: str) -> str:
        """Reject mounting the blog blueprint at the site root.

        The root path is reserved for the homepage route, which dispatches to
        either the configured homepage content or the blog index as a fallback.
        """
        if prefix == "/":
            raise ValueError(
                'BLOG_PREFIX cannot be "/" — the root path is reserved for the homepage route. '
                'Use a prefix such as "/blog" instead.'
            )
        return prefix

    @model_validator(mode="before")
    @classmethod
    def fill_default_language(cls, data: object) -> object:
        """Imply DEFAULT_LANGUAGE: the first configured language, otherwise ``en``."""
        if not isinstance(data, dict) or data.get("DEFAULT_LANGUAGE"):
            return data
        languages = data.get("LANGUAGES") or {}
        implied = next(iter(languages), "en")
        return {**data, "DEFAULT_LANGUAGE": implied}

    @model_validator(mode="after")
    def validate_language_urls(self) -> "Config":
        """Ensure every configured language is served at exactly one URL.

        Raises:
            ValueError: If the default language is not configured, two languages share a
                domain, another language has a domain while the default does not, or a
                language's code cannot be used as a URL segment.
        """
        if not self.languages:
            return self
        if self.default_language not in self.languages:
            raise ValueError(
                f"DEFAULT_LANGUAGE {self.default_language!r} is not one of the configured "
                f"LANGUAGES: {', '.join(self.languages)}"
            )
        domain_owners: dict[str, str] = {}
        for lang_code, language in self.languages.items():
            domain = language.domain
            if domain is None:
                continue
            if domain in domain_owners:
                raise ValueError(
                    f"Languages {domain_owners[domain]!r} and {lang_code!r} share the domain "
                    f"{domain!r}; each language needs its own URL."
                )
            domain_owners[domain] = lang_code
        if domain_owners and self.languages[self.default_language].domain is None:
            raise ValueError(
                f"DEFAULT_LANGUAGE {self.default_language!r} needs a domain because other "
                "languages have one; pages on their domains link back to it."
            )
        prefix_segments = {p.strip("/").split("/")[0] for p in (self.blog_prefix, self.seo_prefix)}
        reserved = RESERVED_PATH_SEGMENTS | (prefix_segments - {""})
        for lang_code in self.languages:
            if lang_code in reserved or not _PATH_SEGMENT.fullmatch(lang_code):
                raise ValueError(
                    f"Language code {lang_code!r} is used as a URL segment (/{lang_code}/), so it "
                    "must use only letters, digits, '-' or '_' and must not be one of: "
                    f"{', '.join(sorted(reserved))}"
                )
        return self

    @cached_property
    def site_languages(self) -> SiteLanguages:
        """The configured languages as URL routing sees them."""
        return SiteLanguages(
            domains={lang_code: language.domain for lang_code, language in self.languages.items()},
            default=self.default_language,
        )

    @property
    def domainless_languages(self) -> tuple[str, ...]:
        """Codes of the languages without their own domain, served under ``/<lang_code>/``."""
        return self.site_languages.domainless_languages

    @field_validator("feature_flags", mode="before")
    @classmethod
    def validate_feature_flags(cls, v: FeatureFlagSet | dict[str, bool] | None) -> FeatureFlagSet:
        """Coerce dict or None into a FeatureFlagSet."""
        if isinstance(v, FeatureFlagSet):
            return v
        if isinstance(v, dict):
            return FeatureFlagSet(v)
        if v is None:
            return FeatureFlagSet({})
        return v

    @classmethod
    def model_validate(
        cls,
        obj: dict[str, t.Any],
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict[str, t.Any] | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
        extra: ExtraValues | None = None,
    ) -> "Config":
        """Validate and construct Config from dictionary.

        Parses the raw FEATURE_FLAGS dict into a ``FeatureFlagSet``.

        Args:
            obj: Configuration dictionary
            strict: Enable strict validation
            from_attributes: Populate from object attributes
            context: Additional validation context
            by_alias: Whether to use field aliases
            by_name: Whether to use field names
            extra: Extra fields handling

        Returns:
            Validated Config instance
        """
        try:
            db_section = obj["DB"]
            db_type = db_section["TYPE"]
        except KeyError as e:
            raise ValueError(f"Missing required config key: {e}. DB.TYPE is required.") from e
        db_cfg_type = get_db_module(db_type).db_config_type()
        obj["DB"] = db_cfg_type.model_validate(db_section)

        return super().model_validate(
            obj,
            strict=strict,
            from_attributes=from_attributes,
            context=context,
            by_alias=by_alias,
            by_name=by_name,
            extra=extra,
        )

    @classmethod
    def parse_yaml(cls, path: str) -> "Config":
        """Parse configuration from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            Validated Config instance

        Raises:
            SystemExit: If config file is missing, unreadable, or not valid YAML
        """
        try:
            with open(path, "r") as f:
                return cls.model_validate(yaml.safe_load(f))
        except FileNotFoundError:
            print(f"Config file not found: {path}", file=sys.stderr)
            raise SystemExit(1)
        except OSError as e:
            print(f"Cannot read config file {path}: {e}", file=sys.stderr)
            raise SystemExit(1)
        except yaml.YAMLError as e:
            print(f"Invalid YAML in config file {path}: {e}", file=sys.stderr)
            raise SystemExit(1)
