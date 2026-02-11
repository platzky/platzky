"""Configuration module for Platzky application.

This module defines all configuration models and parsing logic for the application.
"""

import sys
import typing as t

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.config import ExtraValues

from platzky.attachment.constants import BLOCKED_EXTENSIONS, DEFAULT_MAX_ATTACHMENT_SIZE
from platzky.db.db import DBConfig
from platzky.db.db_loader import get_db_module
from platzky.feature_flags_wrapper import FeatureFlagSet


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


Languages = dict[str, LanguageConfig]
LanguagesMapping = t.Mapping[str, t.Mapping[str, str]]

# Validation error messages
_INVALID_ENDPOINT_FORMAT_MSG = (
    "Invalid endpoint: '{}'. Must be host:port or [http|https]://host[:port]"
)
_INVALID_ENDPOINT_SCHEME_MSG = "Invalid endpoint scheme: '{}'. Must be http or https"
_MISSING_HOSTNAME_MSG = "Invalid endpoint: '{}'. Missing hostname"


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


class TelemetryConfig(BaseModel):
    """OpenTelemetry configuration for application tracing.

    Attributes:
        enabled: Enable or disable telemetry tracing
        endpoint: OTLP gRPC endpoint (e.g., localhost:4317 or http://localhost:4317)
        console_export: Export traces to console for debugging
        timeout: Timeout in seconds for exporter (default: 10)
        deployment_environment: Deployment environment (e.g., production, staging, dev)
        service_instance_id: Service instance ID (auto-generated if not provided)
        flush_on_request: Flush spans after each request (default: True, may impact latency)
        flush_timeout_ms: Timeout in milliseconds for per-request flush (default: 5000)
        instrument_logging: Enable automatic logging instrumentation (default: True)
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    endpoint: t.Optional[str] = None
    console_export: bool = False
    timeout: int = Field(default=10, gt=0)
    deployment_environment: t.Optional[str] = None
    service_instance_id: t.Optional[str] = None
    flush_on_request: bool = True
    flush_timeout_ms: int = Field(default=5000, gt=0)
    instrument_logging: bool = True

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: t.Optional[str]) -> t.Optional[str]:
        """Validate endpoint URL format.

        Accepts OTLP/gRPC spec-compliant formats:
        - host:port (e.g., localhost:4317)
        - http://host[:port]
        - https://host[:port]

        Note: grpc:// scheme is NOT supported per OTLP spec and will be rejected.
        """
        if v is None:
            return v

        from urllib.parse import urlparse

        # Check if it has a scheme (contains ://)
        if "://" not in v:
            # Must be host:port format - validate it has a colon
            if ":" in v and not v.startswith("/"):
                return v
            raise ValueError(_INVALID_ENDPOINT_FORMAT_MSG.format(v))

        # Parse URL with scheme
        parsed = urlparse(v)

        # Validate scheme (only http/https per OTLP spec, grpc is NOT supported)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(_INVALID_ENDPOINT_SCHEME_MSG.format(parsed.scheme))

        # Validate hostname exists
        if not parsed.hostname:
            raise ValueError(_MISSING_HOSTNAME_MSG.format(v))

        return v


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
        translation_directories: Additional translation directories
        debug: Enable debug mode
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
    blog_prefix: str = Field(default="/", alias="BLOG_PREFIX")
    languages: Languages = Field(default_factory=dict, alias="LANGUAGES")
    translation_directories: list[str] = Field(
        default_factory=list,
        alias="TRANSLATION_DIRECTORIES",
    )
    debug: bool = Field(default=False, alias="DEBUG")
    testing: bool = Field(default=False, alias="TESTING")
    feature_flags: FeatureFlagSet = Field(
        default_factory=lambda: FeatureFlagSet({}),
        alias="FEATURE_FLAGS",
    )
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig, alias="TELEMETRY")
    attachment: AttachmentConfig = Field(default_factory=AttachmentConfig, alias="ATTACHMENT")

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
            SystemExit: If config file is not found
        """
        try:
            with open(path, "r") as f:
                return cls.model_validate(yaml.safe_load(f))
        except FileNotFoundError:
            print(f"Config file not found: {path}", file=sys.stderr)
            raise SystemExit(1)
