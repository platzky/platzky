"""Notification system types and protocols.

This module provides notifier protocols for the platzky notification system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from platzky.attachment import AttachmentProtocol


class Notifier(Protocol):
    """Protocol for simple notification handlers (message only).

    Example:
        def slack_notifier(message: str) -> None:
            slack.post(message)

        engine.add_notifier(slack_notifier)
    """

    def __call__(self, message: str) -> None: ...


class NotifierWithAttachments(Protocol):
    """Protocol for notification handlers that support attachments.

    Example:
        def email_notifier(message: str, attachments: list | None = None) -> None:
            send_email(message, attachments=attachments)

        engine.add_notifier_with_attachments(email_notifier)
    """

    def __call__(
        self, message: str, attachments: list[AttachmentProtocol] | None = None
    ) -> None: ...
