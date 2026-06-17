"""Pydantic config models shared between the DB layer and the plugin loader."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PluginConfigBase(BaseModel):
    """Validated name and config from DB. Extra fields are preserved for subclass re-validation."""

    model_config = ConfigDict(extra="allow")
    is_active: bool = False
    config: dict[str, Any] = Field(default_factory=dict)
