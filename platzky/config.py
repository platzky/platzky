import sys
import typing as t

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .db.db import DBConfig
from .db.db_loader import get_db_module


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class LanguageConfig(StrictBaseModel):
    name: str = Field(alias="name")
    flag: str = Field(alias="flag")
    country: str = Field(alias="country")
    domain: t.Optional[str] = Field(default=None, alias="domain")


Languages = dict[str, LanguageConfig]
LanguagesMapping = t.Mapping[str, t.Mapping[str, str]]


def languages_dict(languages: Languages) -> LanguagesMapping:
    return {name: lang.model_dump() for name, lang in languages.items()}


class TelemetryConfig(StrictBaseModel):
    enabled: bool = Field(default=False, alias="enabled")
    exporter: str = Field(default="console", alias="exporter")  # console, otlp, gcp-trace
    otlp_endpoint: t.Optional[str] = Field(default=None, alias="otlp_endpoint")
    console_export: bool = Field(default=False, alias="console_export")


class Config(StrictBaseModel):
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
    feature_flags: t.Optional[dict[str, bool]] = Field(default_factory=dict, alias="FEATURE_FLAGS")
    telemetry: TelemetryConfig = Field(
        default_factory=TelemetryConfig, alias="TELEMETRY"
    )

    @classmethod
    def model_validate(
        cls,
        obj: t.Any,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict[str, t.Any] | None = None,
    ) -> "Config":
        db_cfg_type = get_db_module(obj["DB"]["TYPE"]).db_config_type()
        obj["DB"] = db_cfg_type.model_validate(obj["DB"])
        return super().model_validate(
            obj, strict=strict, from_attributes=from_attributes, context=context
        )

    @classmethod
    def parse_yaml(cls, path: str) -> "Config":
        try:
            with open(path, "r") as f:
                return cls.model_validate(yaml.safe_load(f))
        except FileNotFoundError:
            print(f"Config file not found: {path}", file=sys.stderr)
            raise SystemExit(1)
