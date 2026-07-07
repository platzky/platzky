"""Pydantic config models shared between the DB layer and the plugin loader."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from platzky.content_types import ContentType
from platzky.notification_topics import NotificationTopic


class PluginConfigBase(BaseModel):
    """Validated name and config from DB. Extra fields are preserved for subclass re-validation."""

    model_config = ConfigDict(extra="allow")
    name: str
    config: dict[str, Any] = Field(default_factory=dict)


class NotifyPluginConfig(PluginConfigBase):
    """Plugin config for NotifierPluginBase plugins — carries the topic allowlist."""

    allowed_topics: frozenset[NotificationTopic] = frozenset()


class ContentTransformerPluginConfig(PluginConfigBase):
    """Plugin config for ContentTransformerPluginBase — carries the content-type allowlist."""

    allowed_content_types: frozenset[ContentType] = frozenset()
