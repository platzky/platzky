"""Notification result types and policies.

This module provides the result types and policies for the notification system:
- AttachmentDropPolicy: How to handle unsupported attachments
- AttachmentDropError: Exception for attachment drop failures
- NotifierResult: Result of a single notifier call
- NotificationResult: Aggregated results from all notifiers
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AttachmentDropPolicy(Enum):
    """Policy for handling attachments when a notifier doesn't support them.

    Values:
        WARN: Log a warning and proceed without attachments (default, backward compatible).
              WARNING: This may lead to silent data loss if attachments are critical.
        ERROR: Raise an AttachmentDropError exception, preventing notification.
        SKIP_NOTIFIER: Skip the notifier entirely and log a warning.
    """

    WARN = "warn"
    ERROR = "error"
    SKIP_NOTIFIER = "skip_notifier"


class AttachmentDropError(Exception):
    """Raised when attachments would be dropped and policy is ERROR.

    Attributes:
        notifier_name: Name of the notifier that doesn't support attachments.
        attachment_count: Number of attachments that would be dropped.
    """

    def __init__(self, notifier_name: str, attachment_count: int) -> None:
        self.notifier_name = notifier_name
        self.attachment_count = attachment_count
        super().__init__(
            f"Notifier '{notifier_name}' does not support attachments. "
            f"{attachment_count} attachment(s) would be dropped. "
            f"Either upgrade the notifier or change attachment_drop_policy."
        )


@dataclass
class NotifierResult:
    """Result of sending notification to a single notifier.

    Attributes:
        notifier_name: Name of the notifier.
        received_attachments: Whether the notifier received attachments.
        skipped: Whether the notifier was skipped entirely.
        attachments_dropped: Number of attachments dropped (0 if received or skipped).
    """

    notifier_name: str
    received_attachments: bool = False
    skipped: bool = False
    attachments_dropped: int = 0


@dataclass
class NotificationResult:
    """Result of sending notifications to all notifiers.

    Attributes:
        notifier_results: List of results for each notifier.
        total_notifiers: Total number of registered notifiers.
        notifiers_with_attachments: Number of notifiers that received attachments.
        notifiers_without_attachments: Number of notifiers that didn't receive attachments.
        notifiers_skipped: Number of notifiers that were skipped.
    """

    notifier_results: list[NotifierResult] = field(default_factory=list)

    @property
    def total_notifiers(self) -> int:
        return len(self.notifier_results)

    @property
    def notifiers_with_attachments(self) -> int:
        return sum(1 for r in self.notifier_results if r.received_attachments)

    @property
    def notifiers_without_attachments(self) -> int:
        return sum(1 for r in self.notifier_results if not r.received_attachments and not r.skipped)

    @property
    def notifiers_skipped(self) -> int:
        return sum(1 for r in self.notifier_results if r.skipped)
