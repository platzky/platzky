"""Closed set of content types for plugin filtering."""

from typing import Literal, get_args

ContentType = Literal["post", "page", "comment", "field"]
ALL_CONTENT_TYPES: frozenset[ContentType] = frozenset(get_args(ContentType))
