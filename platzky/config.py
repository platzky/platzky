"""Configuration module for Platzky application.

This module defines all configuration models and parsing logic for the application.
"""

import sys
import typing as t

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .db.db import DBConfig
from .db.db_loader import get_db_module


class StrictBaseModel(BaseModel):
    """Base model with immutable (frozen) configuration."""

    model_config = ConfigDict(frozen=True)


class LanguageConfig(StrictBaseModel):
    """Configuration for a single language.

    Attributes:
        name: Display name of the language
        flag: Flag icon code (country code)
        country: Country code
        domain: Optional domain specific to this language
    """

    name: str = Field(alias="name")
    flag: str = Field(alias="flag")
    country: str = Field(alias="country")
    domain: t.Optional[str] = Field(default=None, alias="domain")


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


class TelemetryConfig(StrictBaseModel):
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

    enabled: bool = Field(default=False, alias="enabled")
    endpoint: t.Optional[str] = Field(default=None, alias="endpoint")
    console_export: bool = Field(default=False, alias="console_export")
    timeout: int = Field(default=10, alias="timeout", gt=0)
    deployment_environment: t.Optional[str] = Field(default=None, alias="deployment_environment")
    service_instance_id: t.Optional[str] = Field(default=None, alias="service_instance_id")
    flush_on_request: bool = Field(default=True, alias="flush_on_request")
    flush_timeout_ms: int = Field(default=5000, alias="flush_timeout_ms", gt=0)
    instrument_logging: bool = Field(default=True, alias="instrument_logging")

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


class Config(StrictBaseModel):
    """Main application configuration.

    Attributes:
        app_name: Application name
        secret_key: Flask secret key for sessions
        db: Database configuration
        use_www: Redirect non-www to www URLs
        seo_prefix: URL prefix for SEO routes
        blog_prefix: URL prefix for blog routes
        languages: Supported languages configuration
        domain_to_lang: Domain to language mapping
        translation_directories: Additional translation directories
        debug: Enable debug mode
        testing: Enable testing mode
        feature_flags: Feature flag configuration
        telemetry: OpenTelemetry configuration
    """

    app_name: str = Field(alias="APP_NAME")
    secret_key: str = Field(alias="SECRET_KEY")
    db: DBConfig = Field(alias="DB")
    use_www: bool = Field(default=True, alias="USE_WWW")
    seo_prefix: str = Field(default="/", alias="SEO_PREFIX")
    blog_prefix: str = Field(default="/", alias="BLOG_PREFIX")
    languages: Languages = Field(default_factory=dict, alias="LANGUAGES")
    domain_to_lang: dict[str, str] = Field(default_factory=dict, alias="DOMAIN_TO_LANG")
    translation_directories: list[str] = Field(
        default_factory=list,
        alias="TRANSLATION_DIRECTORIES",
    )
    debug: bool = Field(default=False, alias="DEBUG")
    testing: bool = Field(default=False, alias="TESTING")
    feature_flags: t.Optional[dict[str, bool]] = Field(default=None, alias="FEATURE_FLAGS")
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig, alias="TELEMETRY")

    @classmethod
    def model_validate(
        cls,
        obj: t.Any,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict[str, t.Any] | None = None,
    ) -> "Config":
        """Validate and construct Config from dictionary.

        Args:
            obj: Configuration dictionary
            strict: Enable strict validation
            from_attributes: Populate from object attributes
            context: Additional validation context

        Returns:
            Validated Config instance
        """
        db_cfg_type = get_db_module(obj["DB"]["TYPE"]).db_config_type()
        obj["DB"] = db_cfg_type.model_validate(obj["DB"])
        return super().model_validate(
            obj, strict=strict, from_attributes=from_attributes, context=context
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
