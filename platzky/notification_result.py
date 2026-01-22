"""Notification result types.

This module provides the result types for the notification system:
- NotifierResult: Result of a single notifier call
- NotificationResult: Aggregated results from all notifiers
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NotifierResult:
    """Result of sending notification to a single notifier.

    Attributes:
        notifier_name: Name of the notifier.
        received_attachments: Whether the notifier received attachments.
    """

    notifier_name: str
    received_attachments: bool = False


@dataclass
class NotificationResult:
    """Result of sending notifications to all notifiers.

    Attributes:
        notifier_results: List of results for each notifier.
        total_notifiers: Total number of registered notifiers.
        notifiers_with_attachments: Number of notifiers that received attachments.
    """

    notifier_results: list[NotifierResult] = field(default_factory=list)

    @property
    def total_notifiers(self) -> int:
        return len(self.notifier_results)

    @property
    def notifiers_with_attachments(self) -> int:
        return sum(1 for r in self.notifier_results if r.received_attachments)
