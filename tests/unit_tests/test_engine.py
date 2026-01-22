import inspect
import logging
from pathlib import Path
from typing import cast

import pytest
from bs4 import BeautifulSoup, Tag
from werkzeug.test import TestResponse

from platzky.config import Config
from platzky.db.json_db import Json
from platzky.engine import (
    AttachmentDropError,
    AttachmentDropPolicy,
    Engine,
    NotificationResult,
)
from platzky.models import CmsModule
from platzky.notifier import (
    DEFAULT_ALLOWED_MIME_TYPES,
    DEFAULT_MAX_ATTACHMENT_SIZE,
    DISCORD_MAX_SIZE,
    EMAIL_MAX_SIZE,
    MAGIC_BYTES,
    SLACK_MAX_SIZE,
    TELEGRAM_MAX_SIZE,
    Attachment,
    AttachmentSizeError,
    ContentMismatchError,
)
from platzky.platzky import create_app_from_config
from tests.unit_tests.fake_app import test_app

test_app = test_app


def test_babel_gets_proper_directories(test_app: Engine):
    with test_app.app_context():
        assert "/some/fake/dir" in list(test_app.babel.domain_instance.translation_directories)


def test_logo_has_set_src(test_app: Engine):
    app = test_app.test_client()
    response = app.get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    found_image = soup.find("img")
    assert isinstance(found_image, Tag)
    assert found_image.get("src") is not None
    assert found_image.get("src") == "https://example.com/logo.png"


def test_if_name_is_shown_if_there_is_no_logo(test_app: Engine):
    cast(Json, test_app.db).data["site_content"].pop("logo_url")
    app = test_app.test_client()
    response = app.get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    assert soup.find("img") is None
    branding = soup.find("a", {"class": "navbar-brand"})
    assert branding is not None
    assert branding.get_text() == "testing App Name"


def test_favicon_is_applied(test_app: Engine):
    cast(Json, test_app.db).data["site_content"]["favicon_url"] = "https://example.com/favicon.ico"
    app = test_app.test_client()
    response = app.get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    found_ico = soup.find("link", rel="icon")
    assert found_ico is not None
    assert isinstance(found_ico, Tag)
    assert found_ico.get("href") is not None
    assert found_ico.get("href") == "https://example.com/favicon.ico"


def test_notifier(test_app: Engine):
    engine = test_app
    notifier_msg = None

    def notifier(message: str) -> None:
        nonlocal notifier_msg
        notifier_msg = message

    engine.add_notifier(notifier)
    engine.notify("test")
    assert notifier_msg == "test"


@pytest.mark.parametrize("content_type", ["body", "head"])
def test_dynamic_content(test_app: Engine, content_type: str):
    def add_dynamic_element(engine: Engine, content: str) -> None:
        getattr(engine, f"add_dynamic_{content_type}")(content)

    def get_content_text(response: TestResponse, content_type: str) -> str:
        soup = BeautifulSoup(response.data, "html.parser")
        return getattr(soup, content_type).get_text()

    add_dynamic_element(test_app, "test1")
    add_dynamic_element(test_app, "test2")
    app = test_app.test_client()
    response = app.get("/blog/page/test")
    content = get_content_text(response, content_type)
    assert "test1" in content
    assert "test2" in content


@pytest.mark.parametrize("use_www", [True, False])
def test_www_redirects(use_www: bool):
    config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "secret",
        "USE_WWW": use_www,
        "BLOG_PREFIX": "/blog",
        "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
        "DB": {
            "TYPE": "json",
            "DATA": {
                "site_content": {
                    "pages": [{"title": "test", "slug": "test", "contentInMarkdown": "test"}],
                }
            },
        },
    }
    config = Config.model_validate(config_data)
    app = create_app_from_config(config)
    client = app.test_client()
    client.allow_subdomain_redirects = True

    if use_www:
        url = "http://localhost/blog/page/test"
        expected_redirect = "http://www.localhost/blog/page/test"
    else:
        url = "http://www.localhost/blog/page/test"
        expected_redirect = "http://localhost/blog/page/test"

    response = client.get(url, follow_redirects=False)

    assert response.request.url == url
    assert response.location == expected_redirect


def test_that_default_page_title_is_app_name(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    assert soup.title is not None
    assert soup.title.string == "testing App Name"


@pytest.mark.parametrize(
    "tag, subtag, value", [("link", "hreflang", "en"), ("html", "lang", "en-GB")]
)
def test_that_tag_has_proper_value(test_app: Engine, tag: str, subtag: str, value: str):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    assert getattr(soup, tag) is not None
    assert getattr(soup, tag).get(subtag) == value


def test_that_logo_has_proper_alt_text(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    logo_img = soup.find("img", class_="logo")
    assert isinstance(logo_img, Tag)
    assert logo_img.get("alt") == "testing App Name logo"


def test_that_logo_link_has_proper_aria_label_text(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    logo_link = soup.find("a", class_="navbar-brand")
    assert isinstance(logo_link, Tag)
    assert logo_link.get("aria-label") == "Link to home page"


def test_that_language_menu_has_proper_code(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    language_menu = soup.find("span", class_="language-indicator-text")
    assert isinstance(language_menu, Tag)
    assert language_menu.get_text() == "en"


def test_that_language_switch_has_proper_aria_label_text(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    logo_link = soup.find("button", id="languages-menu")
    assert isinstance(logo_link, Tag)
    assert (
        logo_link.get("aria-label")
        == "Language switch icon, used to change the language of the website"
    )


def test_that_page_has_proper_html_lang_attribute(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    assert soup.html is not None
    assert soup.html.get("lang") == "en-GB"


def test_add_login_method(test_app: Engine):
    def sample_login_method():
        return "Login Method"

    test_app.add_login_method(sample_login_method)
    assert sample_login_method in test_app.login_methods

    app = test_app.test_client()
    response = app.get("/admin/", follow_redirects=True)

    assert response.status_code == 200
    assert b"Login Method" in response.data


def test_add_cms_module(test_app: Engine):
    module = CmsModule(
        slug="test-module", template="test.html", name="Test Module", description="Test Description"
    )
    test_app.add_cms_module(module)
    assert module in test_app.cms_modules


def test_health_liveness_endpoint(test_app: Engine):
    """Test that /health/liveness returns alive status"""
    client = test_app.test_client()
    response = client.get("/health/liveness")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "alive"


def test_health_alias_endpoint(test_app: Engine):
    """Test that /health is an alias for /health/liveness"""
    client = test_app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "alive"


def test_health_readiness_endpoint_healthy(test_app: Engine):
    """Test that /health/readiness returns ready when database is ok"""
    client = test_app.test_client()
    response = client.get("/health/readiness")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "ready"
    assert json_data["checks"]["database"] == "ok"


def test_health_readiness_endpoint_db_failure(test_app: Engine):
    """Test that /health/readiness returns not_ready when database fails"""
    # Make the database raise an error
    original_method = test_app.db.health_check

    def mock_db_failure():
        raise Exception("DB connection failed")

    test_app.db.health_check = mock_db_failure

    client = test_app.test_client()
    response = client.get("/health/readiness")
    assert response.status_code == 503
    json_data = response.get_json()
    assert json_data["status"] == "not_ready"
    assert "failed: DB connection failed" in json_data["checks"]["database"]

    # Restore original method
    test_app.db.health_check = original_method


def test_add_health_check_success(test_app: Engine):
    """Test adding a custom health check that succeeds"""
    check_called = []

    def custom_check():
        check_called.append(True)

    test_app.add_health_check("custom_service", custom_check)

    client = test_app.test_client()
    response = client.get("/health/readiness")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "ready"
    assert json_data["checks"]["custom_service"] == "ok"
    assert len(check_called) == 1


def test_add_health_check_failure(test_app: Engine):
    """Test adding a custom health check that fails"""

    def failing_check():
        raise Exception("Custom service unavailable")

    test_app.add_health_check("failing_service", failing_check)

    client = test_app.test_client()
    response = client.get("/health/readiness")
    assert response.status_code == 503
    json_data = response.get_json()
    assert json_data["status"] == "not_ready"
    assert "failed: Custom service unavailable" in json_data["checks"]["failing_service"]


def test_multiple_health_checks(test_app: Engine):
    """Test multiple custom health checks with mixed results"""

    def check_ok():
        pass

    def check_fail():
        raise Exception("Service down")

    test_app.add_health_check("service1", check_ok)
    test_app.add_health_check("service2", check_fail)

    client = test_app.test_client()
    response = client.get("/health/readiness")
    assert response.status_code == 503
    json_data = response.get_json()
    assert json_data["status"] == "not_ready"
    assert json_data["checks"]["service1"] == "ok"
    assert "failed: Service down" in json_data["checks"]["service2"]
    assert json_data["checks"]["database"] == "ok"


def test_health_check_db_timeout(test_app: Engine):
    """Test that database health check times out and doesn't block"""
    from concurrent.futures import TimeoutError
    from unittest.mock import patch

    with patch("platzky.engine.ThreadPoolExecutor") as mock_executor_class:
        mock_executor = mock_executor_class.return_value
        mock_future = mock_executor.submit.return_value
        # Simulate timeout
        mock_future.result.side_effect = TimeoutError()

        client = test_app.test_client()
        response = client.get("/health/readiness")

        assert response.status_code == 503
        json_data = response.get_json()
        assert json_data["status"] == "not_ready"
        assert json_data["checks"]["database"] == "failed: timeout"

        # Verify shutdown was called with wait=False
        mock_executor.shutdown.assert_called_with(wait=False)


def test_health_check_custom_timeout(test_app: Engine):
    """Test that custom health check times out and doesn't block"""
    from concurrent.futures import TimeoutError
    from unittest.mock import MagicMock, patch

    def dummy_check():
        pass

    test_app.add_health_check("slow_service", dummy_check)

    with patch("platzky.engine.ThreadPoolExecutor") as mock_executor_class:
        # Single executor is used for all checks
        mock_executor = mock_executor_class.return_value

        # Create two futures - one for db check, one for custom check
        mock_futures = [MagicMock(), MagicMock()]
        mock_executor.submit.side_effect = mock_futures

        # First future (DB check) succeeds
        mock_futures[0].result.return_value = None

        # Second future (custom check) times out
        mock_futures[1].result.side_effect = TimeoutError()

        client = test_app.test_client()
        response = client.get("/health/readiness")

        assert response.status_code == 503
        json_data = response.get_json()
        assert json_data["status"] == "not_ready"
        assert json_data["checks"]["slow_service"] == "failed: timeout"

        # Verify executor was shut down once with wait=False
        mock_executor.shutdown.assert_called_once_with(wait=False)


def test_add_health_check_not_callable(test_app: Engine):
    """Test that adding a non-callable health check raises TypeError"""
    with pytest.raises(TypeError, match="check_function must be callable"):
        test_app.add_health_check("invalid", "not a function")  # type: ignore[arg-type] - Intentionally passing invalid type to test error handling


# =============================================================================
# Attachment Tests
# =============================================================================


class TestAttachment:
    """Tests for the Attachment dataclass validation."""

    def test_valid_attachment(self):
        """Test creating a valid attachment."""
        # Use valid PDF magic bytes
        pdf_content = b"%PDF-1.7 content here"
        attachment = Attachment(
            filename="test.pdf",
            content=pdf_content,
            mime_type="application/pdf",
        )
        assert attachment.filename == "test.pdf"
        assert attachment.content == pdf_content
        assert attachment.mime_type == "application/pdf"

    def test_empty_filename_raises_error(self):
        """Test that empty filename raises ValueError."""
        with pytest.raises(ValueError, match="filename cannot be empty"):
            Attachment(filename="", content=b"content", mime_type="text/plain")

    def test_path_traversal_sanitized(self, caplog: pytest.LogCaptureFixture):
        """Test that path components are stripped from filename."""
        with caplog.at_level(logging.WARNING):
            attachment = Attachment(
                filename="../../../etc/passwd",
                content=b"malicious",
                mime_type="text/plain",
            )
        assert attachment.filename == "passwd"
        assert "path components" in caplog.text

    def test_absolute_path_sanitized(self, caplog: pytest.LogCaptureFixture):
        """Test that absolute paths are sanitized."""
        with caplog.at_level(logging.WARNING):
            attachment = Attachment(
                filename="/etc/passwd",
                content=b"content",
                mime_type="text/plain",
            )
        assert attachment.filename == "passwd"

    def test_windows_path_sanitized(self, caplog: pytest.LogCaptureFixture):
        """Test that Windows-style paths are sanitized."""
        with caplog.at_level(logging.WARNING):
            attachment = Attachment(
                filename="C:\\Users\\test\\file.txt",
                content=b"content",
                mime_type="text/plain",
            )
        # os.path.basename handles this based on OS, but the filename should be sanitized
        assert "/" not in attachment.filename
        assert "\\" not in attachment.filename

    def test_oversized_attachment_raises_error(self):
        """Test that attachment exceeding max size raises ValueError."""
        oversized_content = b"x" * (DEFAULT_MAX_ATTACHMENT_SIZE + 1)
        with pytest.raises(ValueError, match="exceeds maximum size"):
            Attachment(
                filename="large.bin",
                content=oversized_content,
                mime_type="application/zip",
                validate_content=False,  # Skip magic byte validation for size test
            )

    def test_max_size_attachment_allowed(self):
        """Test that attachment at exactly max size is allowed."""
        max_content = b"x" * DEFAULT_MAX_ATTACHMENT_SIZE
        attachment = Attachment(
            filename="max.bin",
            content=max_content,
            mime_type="application/zip",
            validate_content=False,  # Skip magic byte validation for size test
        )
        assert len(attachment.content) == DEFAULT_MAX_ATTACHMENT_SIZE

    def test_invalid_mime_type_format_raises_error(self):
        """Test that invalid MIME type format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid MIME type format"):
            Attachment(filename="file.txt", content=b"content", mime_type="invalid")

    def test_empty_mime_type_raises_error(self):
        """Test that empty MIME type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid MIME type format"):
            Attachment(filename="file.txt", content=b"content", mime_type="")

    def test_disallowed_mime_type_raises_error(self):
        """Test that MIME type not in allowlist raises ValueError."""
        with pytest.raises(ValueError, match="is not allowed"):
            Attachment(
                filename="file.exe",
                content=b"content",
                mime_type="application/x-executable",
            )

    def test_custom_allowed_mime_types_extends_default(self):
        """Test that custom allowed_mime_types extends the default list."""
        custom_type = "application/x-custom"
        attachment = Attachment(
            filename="custom.file",
            content=b"content",
            mime_type=custom_type,
            allowed_mime_types=frozenset({custom_type}),
        )
        assert attachment.mime_type == custom_type

    def test_default_allowed_mime_types_still_work_with_custom(self):
        """Test that default MIME types still work when custom types are provided."""
        # Use valid PDF magic bytes
        attachment = Attachment(
            filename="file.pdf",
            content=b"%PDF-1.7 content",
            mime_type="application/pdf",
            allowed_mime_types=frozenset({"application/x-custom"}),
        )
        assert attachment.mime_type == "application/pdf"

    @pytest.mark.parametrize(
        "mime_type",
        [
            "text/plain",
            "text/html",
            "text/csv",
            "image/png",
            "image/jpeg",
            "image/gif",
            "application/pdf",
            "application/json",
            "application/xml",
            "application/zip",
        ],
    )
    def test_common_mime_types_are_allowed(self, mime_type: str):
        """Test that common MIME types are in the default allowlist."""
        # Skip magic byte validation to test MIME type allowlist independently
        attachment = Attachment(
            filename="test.file",
            content=b"content",
            mime_type=mime_type,
            validate_content=False,
        )
        assert attachment.mime_type == mime_type

    def test_default_allowed_mime_types_constant_is_frozenset(self):
        """Test that DEFAULT_ALLOWED_MIME_TYPES is immutable."""
        assert isinstance(DEFAULT_ALLOWED_MIME_TYPES, frozenset)

    def test_mime_type_validation_with_malicious_format(self):
        """Test that MIME types with valid format but not in allowlist are rejected."""
        with pytest.raises(ValueError, match="is not allowed"):
            Attachment(
                filename="script.sh",
                content=b"#!/bin/bash",
                mime_type="application/x-shellscript",
            )

    def test_attachment_is_immutable(self):
        """Test that attachment is frozen (immutable)."""
        attachment = Attachment(filename="test.txt", content=b"content", mime_type="text/plain")
        with pytest.raises(AttributeError):
            attachment.filename = "changed.txt"  # type: ignore[misc]


# =============================================================================
# Attachment Custom Size Limit Tests
# =============================================================================


class TestAttachmentCustomSizeLimit:
    """Tests for configurable attachment size limits."""

    def test_size_presets_have_correct_values(self):
        """Test that size presets have the expected values."""
        assert DEFAULT_MAX_ATTACHMENT_SIZE == 10 * 1024 * 1024  # 10MB
        assert EMAIL_MAX_SIZE == 10 * 1024 * 1024  # 10MB
        assert SLACK_MAX_SIZE == 5 * 1024 * 1024  # 5MB
        assert DISCORD_MAX_SIZE == 8 * 1024 * 1024  # 8MB
        assert TELEGRAM_MAX_SIZE == 50 * 1024 * 1024  # 50MB

    def test_default_max_size_is_applied(self):
        """Test that default max_size is applied when not specified."""
        attachment = Attachment(
            filename="test.txt",
            content=b"content",
            mime_type="text/plain",
        )
        assert attachment.max_size == DEFAULT_MAX_ATTACHMENT_SIZE

    def test_custom_max_size_is_stored(self):
        """Test that custom max_size is stored on the instance."""
        custom_size = 5 * 1024 * 1024  # 5MB
        attachment = Attachment(
            filename="test.txt",
            content=b"content",
            mime_type="text/plain",
            max_size=custom_size,
        )
        assert attachment.max_size == custom_size

    def test_slack_max_size_preset(self):
        """Test using SLACK_MAX_SIZE preset."""
        attachment = Attachment(
            filename="test.txt",
            content=b"content",
            mime_type="text/plain",
            max_size=SLACK_MAX_SIZE,
        )
        assert attachment.max_size == SLACK_MAX_SIZE
        assert attachment.max_size == 5 * 1024 * 1024

    def test_discord_max_size_preset(self):
        """Test using DISCORD_MAX_SIZE preset."""
        attachment = Attachment(
            filename="test.txt",
            content=b"content",
            mime_type="text/plain",
            max_size=DISCORD_MAX_SIZE,
        )
        assert attachment.max_size == DISCORD_MAX_SIZE
        assert attachment.max_size == 8 * 1024 * 1024

    def test_telegram_max_size_preset(self):
        """Test using TELEGRAM_MAX_SIZE preset."""
        attachment = Attachment(
            filename="test.txt",
            content=b"content",
            mime_type="text/plain",
            max_size=TELEGRAM_MAX_SIZE,
        )
        assert attachment.max_size == TELEGRAM_MAX_SIZE
        assert attachment.max_size == 50 * 1024 * 1024

    def test_custom_size_limit_rejects_oversized_content(self):
        """Test that custom size limit rejects content exceeding it."""
        custom_size = 1 * 1024  # 1KB
        oversized_content = b"x" * (custom_size + 1)
        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment(
                filename="large.txt",
                content=oversized_content,
                mime_type="text/plain",
                max_size=custom_size,
            )

    def test_custom_size_limit_allows_exact_size(self):
        """Test that content at exactly custom size limit is allowed."""
        custom_size = 1 * 1024  # 1KB
        content = b"x" * custom_size
        attachment = Attachment(
            filename="exact.txt",
            content=content,
            mime_type="text/plain",
            max_size=custom_size,
        )
        assert len(attachment.content) == custom_size

    def test_custom_size_limit_allows_smaller_content(self):
        """Test that content smaller than custom size limit is allowed."""
        custom_size = 1 * 1024  # 1KB
        content = b"x" * (custom_size - 1)
        attachment = Attachment(
            filename="small.txt",
            content=content,
            mime_type="text/plain",
            max_size=custom_size,
        )
        assert len(attachment.content) < custom_size

    def test_larger_custom_size_allows_bigger_attachments(self):
        """Test that larger custom size limit allows bigger attachments."""
        # Create content larger than default but smaller than TELEGRAM_MAX_SIZE
        large_content = b"x" * (DEFAULT_MAX_ATTACHMENT_SIZE + 1000)
        attachment = Attachment(
            filename="large.bin",
            content=large_content,
            mime_type="application/zip",
            max_size=TELEGRAM_MAX_SIZE,
            validate_content=False,  # Skip magic byte validation
        )
        assert len(attachment.content) > DEFAULT_MAX_ATTACHMENT_SIZE

    def test_attachment_size_error_message_shows_custom_limit(self):
        """Test that error message shows the custom size limit, not default."""
        custom_size = 2 * 1024 * 1024  # 2MB
        oversized_content = b"x" * (custom_size + 1)
        with pytest.raises(AttachmentSizeError) as exc_info:
            Attachment(
                filename="large.txt",
                content=oversized_content,
                mime_type="text/plain",
                max_size=custom_size,
            )
        error_message = str(exc_info.value)
        assert "2.00MB" in error_message  # Custom limit should be shown

    def test_attachment_size_error_is_value_error_subclass(self):
        """Test that AttachmentSizeError is a subclass of ValueError for backwards compatibility."""
        assert issubclass(AttachmentSizeError, ValueError)

    def test_content_exceeding_slack_limit_but_within_default(self):
        """Test content that exceeds Slack limit but is within default limit."""
        # Content between Slack limit (5MB) and default (10MB)
        content_size = 6 * 1024 * 1024  # 6MB
        content = b"x" * content_size

        # Should fail with Slack limit
        with pytest.raises(AttachmentSizeError):
            Attachment(
                filename="file.txt",
                content=content,
                mime_type="text/plain",
                max_size=SLACK_MAX_SIZE,
            )

        # Should succeed with default limit
        attachment = Attachment(
            filename="file.bin",
            content=content,
            mime_type="application/zip",
            validate_content=False,  # Skip magic byte validation
        )
        assert len(attachment.content) == content_size

    @pytest.mark.parametrize(
        "preset,expected_bytes",
        [
            (EMAIL_MAX_SIZE, 10 * 1024 * 1024),
            (SLACK_MAX_SIZE, 5 * 1024 * 1024),
            (DISCORD_MAX_SIZE, 8 * 1024 * 1024),
            (TELEGRAM_MAX_SIZE, 50 * 1024 * 1024),
        ],
    )
    def test_all_presets_enforce_correct_limits(self, preset: int, expected_bytes: int):
        """Test that all presets enforce their correct limits."""
        # Content at exact limit should pass
        content = b"x" * expected_bytes
        attachment = Attachment(
            filename="file.bin",
            content=content,
            mime_type="application/zip",
            max_size=preset,
            validate_content=False,  # Skip magic byte validation
        )
        assert len(attachment.content) == expected_bytes
        assert attachment.max_size == preset

        # Content over limit should fail
        oversized_content = b"x" * (expected_bytes + 1)
        with pytest.raises(AttachmentSizeError):
            Attachment(
                filename="file.bin",
                content=oversized_content,
                mime_type="application/zip",
                max_size=preset,
                validate_content=False,
            )

    def test_very_small_custom_size_limit(self):
        """Test that very small custom size limits work correctly."""
        small_limit = 10  # 10 bytes
        content = b"hello"  # 5 bytes
        attachment = Attachment(
            filename="tiny.txt",
            content=content,
            mime_type="text/plain",
            max_size=small_limit,
        )
        assert attachment.max_size == small_limit
        assert len(attachment.content) < small_limit

    def test_zero_size_limit_rejects_any_content(self):
        """Test that zero size limit rejects any non-empty content."""
        with pytest.raises(AttachmentSizeError):
            Attachment(
                filename="any.txt",
                content=b"x",
                mime_type="text/plain",
                max_size=0,
            )

    def test_zero_size_limit_allows_empty_content(self):
        """Test that zero size limit allows empty content."""
        attachment = Attachment(
            filename="empty.txt",
            content=b"",
            mime_type="text/plain",
            max_size=0,
        )
        assert attachment.content == b""
        assert attachment.max_size == 0


# =============================================================================
# Attachment Factory Methods Tests
# =============================================================================


class TestAttachmentFromBytes:
    """Tests for the Attachment.from_bytes() factory method."""

    def test_from_bytes_creates_valid_attachment(self):
        """Test that from_bytes creates a valid attachment."""
        content = b"PDF content here"
        attachment = Attachment.from_bytes(
            content=content,
            filename="test.pdf",
            mime_type="application/pdf",
            validate_content=False,
        )
        assert attachment.filename == "test.pdf"
        assert attachment.content == content
        assert attachment.mime_type == "application/pdf"

    def test_from_bytes_validates_size_before_creation(self):
        """Test that from_bytes validates size BEFORE creating the object."""
        # Create content larger than a custom max_size
        large_content = b"x" * 1000
        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment.from_bytes(
                content=large_content,
                filename="large.bin",
                mime_type="application/zip",
                max_size=500,
            )

    def test_from_bytes_with_custom_max_size(self):
        """Test from_bytes with custom max_size smaller than default."""
        content = b"x" * 100
        # Should work with max_size >= content size
        attachment = Attachment.from_bytes(
            content=content,
            filename="test.bin",
            mime_type="application/zip",
            max_size=100,
            validate_content=False,
        )
        assert len(attachment.content) == 100

        # Should fail with max_size < content size
        with pytest.raises(AttachmentSizeError):
            Attachment.from_bytes(
                content=content,
                filename="test.bin",
                mime_type="application/zip",
                max_size=99,
            )

    def test_from_bytes_uses_default_max_size_when_none(self):
        """Test that from_bytes uses DEFAULT_MAX_ATTACHMENT_SIZE when max_size is None."""
        oversized_content = b"x" * (DEFAULT_MAX_ATTACHMENT_SIZE + 1)
        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment.from_bytes(
                content=oversized_content,
                filename="large.bin",
                mime_type="application/zip",
                max_size=None,
            )

    def test_from_bytes_zero_max_size_disables_pre_check(self):
        """Test that max_size=0 disables pre-validation size checking."""
        # Create content larger than default max - should fail at __post_init__
        large_content = b"x" * (DEFAULT_MAX_ATTACHMENT_SIZE + 1)

        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment.from_bytes(
                content=large_content,
                filename="large.bin",
                mime_type="application/zip",
                max_size=0,  # Disables pre-check, but __post_init__ still validates
            )

    def test_from_bytes_sanitizes_filename(self, caplog: pytest.LogCaptureFixture):
        """Test that from_bytes sanitizes filenames with path components."""
        with caplog.at_level(logging.WARNING):
            attachment = Attachment.from_bytes(
                content=b"content",
                filename="../../../etc/passwd",
                mime_type="text/plain",
            )
        assert attachment.filename == "passwd"
        assert "path components" in caplog.text

    def test_from_bytes_raises_on_empty_filename(self):
        """Test that from_bytes raises on empty filename."""
        with pytest.raises(ValueError, match="filename cannot be empty"):
            Attachment.from_bytes(
                content=b"content",
                filename="",
                mime_type="text/plain",
            )

    def test_from_bytes_raises_on_invalid_mime_type(self):
        """Test that from_bytes raises on invalid MIME type."""
        with pytest.raises(ValueError, match="Invalid MIME type"):
            Attachment.from_bytes(
                content=b"content",
                filename="test.bin",
                mime_type="invalid",
            )

    def test_from_bytes_with_allowed_mime_types(self):
        """Test from_bytes with custom allowed_mime_types."""
        custom_type = "application/x-custom"
        attachment = Attachment.from_bytes(
            content=b"content",
            filename="test.custom",
            mime_type=custom_type,
            allowed_mime_types=frozenset({custom_type}),
        )
        assert attachment.mime_type == custom_type

    def test_from_bytes_error_message_includes_sanitized_filename(self):
        """Test that size error uses sanitized filename in message."""
        large_content = b"x" * 1000
        with pytest.raises(AttachmentSizeError) as exc_info:
            Attachment.from_bytes(
                content=large_content,
                filename="../../../secret.bin",
                mime_type="application/zip",
                max_size=500,
            )
        # Error message should contain sanitized filename, not path
        assert "secret.bin" in str(exc_info.value)
        assert "../" not in str(exc_info.value)


class TestAttachmentFromFile:
    """Tests for the Attachment.from_file() factory method."""

    def test_from_file_creates_valid_attachment(self, tmp_path: Path):
        """Test that from_file creates a valid attachment."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Hello, World!")

        attachment = Attachment.from_file(
            file_path=test_file,
            mime_type="text/plain",  # Override guessed type
        )
        assert attachment.filename == "test.txt"
        assert attachment.content == b"Hello, World!"
        assert attachment.mime_type == "text/plain"

    def test_from_file_validates_size_before_reading(self, tmp_path: Path):
        """Test that from_file checks file size BEFORE reading content."""
        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b"x" * 1000)

        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment.from_file(
                file_path=large_file,
                mime_type="application/zip",
                max_size=500,
            )

    def test_from_file_with_custom_filename(self, tmp_path: Path):
        """Test from_file with custom filename override."""
        test_file = tmp_path / "original.txt"
        test_file.write_bytes(b"content")

        attachment = Attachment.from_file(
            file_path=test_file,
            filename="custom.txt",
            mime_type="text/plain",
        )
        assert attachment.filename == "custom.txt"

    def test_from_file_uses_basename_when_no_filename(self, tmp_path: Path):
        """Test that from_file uses file basename when filename is None."""
        test_file = tmp_path / "myfile.txt"
        test_file.write_bytes(b"content")

        attachment = Attachment.from_file(
            file_path=test_file,
            filename=None,
            mime_type="text/plain",
        )
        assert attachment.filename == "myfile.txt"

    def test_from_file_guesses_mime_type(self, tmp_path: Path):
        """Test that from_file guesses MIME type from filename."""
        pdf_file = tmp_path / "document.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")

        attachment = Attachment.from_file(
            file_path=pdf_file,
            mime_type=None,  # Let it guess
            validate_content=False,  # Skip magic byte validation
        )
        assert attachment.mime_type == "application/pdf"

    def test_from_file_falls_back_to_octet_stream(self, tmp_path: Path):
        """Test that from_file falls back to application/octet-stream for unknown types."""
        unknown_file = tmp_path / "unknown.xyz123"
        unknown_file.write_bytes(b"content")

        attachment = Attachment.from_file(
            file_path=unknown_file,
            mime_type=None,
            allowed_mime_types=frozenset({"application/octet-stream"}),
        )
        assert attachment.mime_type == "application/octet-stream"

    def test_from_file_raises_file_not_found(self, tmp_path: Path):
        """Test that from_file raises FileNotFoundError for missing files."""
        missing_file = tmp_path / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            Attachment.from_file(file_path=missing_file)

    def test_from_file_raises_is_directory_error(self, tmp_path: Path):
        """Test that from_file raises error when path is a directory."""
        directory = tmp_path / "subdir"
        directory.mkdir()

        # On some systems this may raise IsADirectoryError or PermissionError
        with pytest.raises((IsADirectoryError, PermissionError)):
            Attachment.from_file(file_path=directory)

    def test_from_file_with_path_object(self, tmp_path: Path):
        """Test from_file with Path object instead of string."""

        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"content")

        # Both string and Path should work
        attachment1 = Attachment.from_file(
            file_path=str(test_file),
            mime_type="text/plain",
        )
        attachment2 = Attachment.from_file(
            file_path=test_file,  # Path object
            mime_type="text/plain",
        )

        assert attachment1.content == attachment2.content
        assert attachment1.filename == attachment2.filename

    def test_from_file_with_custom_max_size(self, tmp_path: Path):
        """Test from_file with custom max_size."""
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"x" * 100)

        # Should work at exactly max size
        attachment = Attachment.from_file(
            file_path=test_file,
            mime_type="application/zip",
            max_size=100,
            validate_content=False,
        )
        assert len(attachment.content) == 100

        # Should fail above max size
        with pytest.raises(AttachmentSizeError):
            Attachment.from_file(
                file_path=test_file,
                mime_type="application/zip",
                max_size=99,
            )

    def test_from_file_uses_default_max_size_when_none(self, tmp_path: Path):
        """Test that from_file uses default max size when None."""
        # Create a file larger than default max (10MB)
        large_file = tmp_path / "large.bin"
        # Only write enough to exceed the limit, not the full 10MB for speed
        large_file.write_bytes(b"x" * (DEFAULT_MAX_ATTACHMENT_SIZE + 1))

        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment.from_file(
                file_path=large_file,
                mime_type="application/zip",
                max_size=None,
            )

    def test_from_file_with_allowed_mime_types(self, tmp_path: Path):
        """Test from_file with custom allowed_mime_types."""
        custom_file = tmp_path / "custom.file"
        custom_file.write_bytes(b"content")

        custom_type = "application/x-custom"
        attachment = Attachment.from_file(
            file_path=custom_file,
            mime_type=custom_type,
            allowed_mime_types=frozenset({custom_type}),
        )
        assert attachment.mime_type == custom_type

    def test_from_file_error_message_includes_filename(self, tmp_path: Path):
        """Test that size error message includes the filename."""
        large_file = tmp_path / "bigfile.bin"
        large_file.write_bytes(b"x" * 1000)

        with pytest.raises(AttachmentSizeError) as exc_info:
            Attachment.from_file(
                file_path=large_file,
                mime_type="application/zip",
                max_size=500,
            )
        assert "bigfile.bin" in str(exc_info.value)


# =============================================================================
# Notifier with Attachments Tests
# =============================================================================


class TestNotifierWithAttachments:
    """Tests for notifier functionality with attachments."""

    def test_notifier_receives_attachments(self, test_app: Engine):
        """Test that notifier with attachments parameter receives them."""
        received_attachments = []

        def notifier_with_attachments(
            _message: str, attachments: list[Attachment] | None = None
        ) -> None:
            received_attachments.append(attachments)

        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(notifier_with_attachments)
        test_app.notify("test message", attachments=[attachment])

        assert len(received_attachments) == 1
        assert received_attachments[0] is not None
        assert len(received_attachments[0]) == 1
        assert received_attachments[0][0].filename == "test.txt"

    def test_legacy_notifier_still_works(self, test_app: Engine):
        """Test that legacy notifier without attachments parameter still works."""
        received_messages = []

        def legacy_notifier(message: str) -> None:
            received_messages.append(message)

        test_app.add_notifier(legacy_notifier)
        test_app.notify("test message")

        assert received_messages == ["test message"]

    def test_legacy_notifier_drops_attachments_with_warning(
        self, test_app: Engine, caplog: pytest.LogCaptureFixture
    ):
        """Test that legacy notifier drops attachments and logs warning."""
        received_messages = []

        def legacy_notifier(message: str) -> None:
            received_messages.append(message)

        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(legacy_notifier)

        with caplog.at_level(logging.WARNING):
            test_app.notify("test message", attachments=[attachment])

        assert received_messages == ["test message"]
        assert "does not support attachments" in caplog.text
        assert "1 attachment(s) will be dropped" in caplog.text

    def test_mixed_notifiers(self, test_app: Engine, caplog: pytest.LogCaptureFixture):
        """Test mixed notifiers - some with attachments, some without."""
        legacy_messages = []
        modern_messages = []
        modern_attachments = []

        def legacy_notifier(message: str) -> None:
            legacy_messages.append(message)

        def modern_notifier(message: str, attachments: list[Attachment] | None = None) -> None:
            modern_messages.append(message)
            modern_attachments.append(attachments)

        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(legacy_notifier)
        test_app.add_notifier(modern_notifier)

        with caplog.at_level(logging.WARNING):
            test_app.notify("test message", attachments=[attachment])

        # Both received the message
        assert legacy_messages == ["test message"]
        assert modern_messages == ["test message"]

        # Only modern notifier received attachments
        assert modern_attachments[0] is not None
        assert len(modern_attachments[0]) == 1

        # Warning logged for legacy notifier
        assert "does not support attachments" in caplog.text

    def test_notify_with_none_attachments(self, test_app: Engine):
        """Test that None attachments work correctly."""
        received_attachments = []

        def notifier(_message: str, attachments: list[Attachment] | None = None) -> None:
            received_attachments.append(attachments)

        test_app.add_notifier(notifier)
        test_app.notify("test", attachments=None)

        assert received_attachments == [None]

    def test_notify_with_empty_attachments_list(self, test_app: Engine):
        """Test that empty attachments list works correctly."""
        received_attachments = []

        def notifier(_message: str, attachments: list[Attachment] | None = None) -> None:
            received_attachments.append(attachments)

        test_app.add_notifier(notifier)
        test_app.notify("test", attachments=[])

        assert received_attachments == [[]]

    def test_notify_with_multiple_attachments(self, test_app: Engine):
        """Test notifying with multiple attachments."""
        received_attachments = []

        def notifier(_message: str, attachments: list[Attachment] | None = None) -> None:
            received_attachments.append(attachments)

        # Use valid magic bytes for binary formats
        attachments = [
            Attachment(filename="file1.txt", content=b"one", mime_type="text/plain"),
            Attachment(
                filename="file2.pdf", content=b"%PDF-1.7 content", mime_type="application/pdf"
            ),
            Attachment(
                filename="file3.png", content=b"\x89PNG\r\n\x1a\n data", mime_type="image/png"
            ),
        ]
        test_app.add_notifier(notifier)
        test_app.notify("test", attachments=attachments)

        assert len(received_attachments[0]) == 3
        assert [a.filename for a in received_attachments[0]] == [
            "file1.txt",
            "file2.pdf",
            "file3.png",
        ]

    def test_notifier_error_propagates(self, test_app: Engine):
        """Test that errors from notifiers propagate correctly."""

        def failing_notifier(_message: str, attachments: list[Attachment] | None = None) -> None:  # noqa: ARG001
            raise RuntimeError("Notifier failed")

        test_app.add_notifier(failing_notifier)

        with pytest.raises(RuntimeError, match="Notifier failed"):
            test_app.notify("test")

    def test_class_based_notifier(self, test_app: Engine):
        """Test that class-based notifiers work correctly."""
        received = []

        class MyNotifier:
            def __call__(self, message: str, attachments: list[Attachment] | None = None) -> None:
                received.append((message, attachments))

        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(MyNotifier())
        test_app.notify("test", attachments=[attachment])

        assert len(received) == 1
        assert received[0][0] == "test"
        assert received[0][1] is not None
        assert received[0][1][0].filename == "test.txt"


# =============================================================================
# Notifier Capability Cache Tests
# =============================================================================


class TestNotifierCapabilityCache:
    """Tests for notifier capability caching."""

    def test_cache_avoids_repeated_signature_inspection(self, test_app: Engine):
        """Test that signature inspection is only called once per notifier."""
        from unittest.mock import patch

        def notifier(_message: str, attachments: list[Attachment] | None = None) -> None:  # noqa: ARG001
            pass

        test_app.add_notifier(notifier)

        with patch("platzky.engine.inspect.signature", wraps=inspect.signature) as mock_sig:
            # First call should inspect
            test_app.notify("test1")
            assert mock_sig.call_count == 1

            # Second call should use cache
            test_app.notify("test2")
            assert mock_sig.call_count == 1

            # Third call should still use cache
            test_app.notify("test3")
            assert mock_sig.call_count == 1

    def test_cache_uses_notifier_id_as_key(self, test_app: Engine):
        """Test that cache uses id(notifier) as key."""

        def notifier(_message: str) -> None:
            pass

        test_app.add_notifier(notifier)
        test_app.notify("test")

        # Check that the cache contains the notifier's id
        assert id(notifier) in test_app._notifier_capability_cache

    def test_clear_notifier_cache(self, test_app: Engine):
        """Test that clear_notifier_cache clears the cache."""
        from unittest.mock import patch

        def notifier(_message: str) -> None:
            pass

        test_app.add_notifier(notifier)

        with patch("platzky.engine.inspect.signature", wraps=inspect.signature) as mock_sig:
            test_app.notify("test1")
            assert mock_sig.call_count == 1

            # Clear cache
            test_app.clear_notifier_cache()
            assert len(test_app._notifier_capability_cache) == 0

            # Next call should inspect again
            test_app.notify("test2")
            assert mock_sig.call_count == 2

    def test_cache_stores_correct_values(self, test_app: Engine):
        """Test that cache stores correct boolean values for different notifiers."""

        def legacy_notifier(_message: str) -> None:
            pass

        def modern_notifier(_message: str, attachments: list[Attachment] | None = None) -> None:  # noqa: ARG001
            pass

        test_app.add_notifier(legacy_notifier)
        test_app.add_notifier(modern_notifier)
        test_app.notify("test")

        assert test_app._notifier_capability_cache[id(legacy_notifier)] is False
        assert test_app._notifier_capability_cache[id(modern_notifier)] is True

    def test_cache_handles_signature_inspection_errors(
        self, test_app: Engine, caplog: pytest.LogCaptureFixture
    ):
        """Test that signature inspection errors are cached and logged."""
        from unittest.mock import MagicMock, patch

        # Create a notifier that will cause signature inspection to fail
        mock_notifier = MagicMock()
        mock_notifier.__name__ = "mock_notifier"

        test_app.add_notifier(mock_notifier)

        with patch(
            "platzky.engine.inspect.signature", side_effect=ValueError("Cannot inspect")
        ) as mock_sig:
            with caplog.at_level(logging.WARNING):
                test_app.notify("test1")

            assert mock_sig.call_count == 1
            assert "Failed to inspect signature" in caplog.text
            assert "Cannot inspect" in caplog.text

            # Verify error result is cached as False
            assert test_app._notifier_capability_cache[id(mock_notifier)] is False

            # Second call should use cache, not call inspect again
            test_app.notify("test2")
            assert mock_sig.call_count == 1

    def test_different_notifier_instances_have_separate_cache_entries(self, test_app: Engine):
        """Test that different instances of same class have separate cache entries."""

        class MyNotifier:
            def __call__(self, _message: str, attachments: list[Attachment] | None = None) -> None:
                pass

        notifier1 = MyNotifier()
        notifier2 = MyNotifier()

        test_app.add_notifier(notifier1)
        test_app.add_notifier(notifier2)
        test_app.notify("test")

        # Both should be cached separately
        assert id(notifier1) in test_app._notifier_capability_cache
        assert id(notifier2) in test_app._notifier_capability_cache
        assert id(notifier1) != id(notifier2)

    def test_cache_is_instance_specific(self):
        """Test that cache is instance-specific, not shared across Engine instances."""
        from platzky.config import Config
        from platzky.db.json_db import Json

        config_data = {
            "APP_NAME": "testApp",
            "SECRET_KEY": "secret",
            "BLOG_PREFIX": "/blog",
            "TRANSLATION_DIRECTORIES": [],
            "DB": {"TYPE": "json", "DATA": {"site_content": {"pages": []}}},
        }
        config = Config.model_validate(config_data)
        db = Json(config.db)

        engine1 = Engine(config, db, "test1")
        engine2 = Engine(config, db, "test2")

        def notifier(_message: str) -> None:
            pass

        engine1.add_notifier(notifier)
        engine1.notify("test")

        # engine1 should have the cache entry
        assert id(notifier) in engine1._notifier_capability_cache

        # engine2 should not have the cache entry
        assert id(notifier) not in engine2._notifier_capability_cache


# =============================================================================
# Magic Byte Content Validation Tests
# =============================================================================


class TestMagicByteValidation:
    """Tests for magic byte content validation in Attachment class."""

    # Valid magic bytes for common file types
    PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
    JPEG_MAGIC = b"\xff\xd8\xff"
    GIF87_MAGIC = b"GIF87a"
    GIF89_MAGIC = b"GIF89a"
    PDF_MAGIC = b"%PDF"
    ZIP_MAGIC = b"PK\x03\x04"
    GZIP_MAGIC = b"\x1f\x8b"
    BMP_MAGIC = b"BM"
    TIFF_LE_MAGIC = b"II\x2a\x00"  # Little-endian
    TIFF_BE_MAGIC = b"MM\x00\x2a"  # Big-endian
    RIFF_MAGIC = b"RIFF"  # Used by WAV, WebP, AVI
    OGG_MAGIC = b"OggS"
    MP3_ID3_MAGIC = b"ID3"
    MP3_SYNC_MAGIC = b"\xff\xfb"

    def test_valid_png_content(self):
        """Test that valid PNG content passes validation."""
        content = self.PNG_MAGIC + b"rest of png data"
        attachment = Attachment(
            filename="image.png",
            content=content,
            mime_type="image/png",
        )
        assert attachment.content == content

    def test_valid_jpeg_content(self):
        """Test that valid JPEG content passes validation."""
        content = self.JPEG_MAGIC + b"rest of jpeg data"
        attachment = Attachment(
            filename="image.jpg",
            content=content,
            mime_type="image/jpeg",
        )
        assert attachment.content == content

    def test_valid_gif87a_content(self):
        """Test that valid GIF87a content passes validation."""
        content = self.GIF87_MAGIC + b"rest of gif data"
        attachment = Attachment(
            filename="image.gif",
            content=content,
            mime_type="image/gif",
        )
        assert attachment.content == content

    def test_valid_gif89a_content(self):
        """Test that valid GIF89a content passes validation."""
        content = self.GIF89_MAGIC + b"rest of gif data"
        attachment = Attachment(
            filename="image.gif",
            content=content,
            mime_type="image/gif",
        )
        assert attachment.content == content

    def test_valid_pdf_content(self):
        """Test that valid PDF content passes validation."""
        content = self.PDF_MAGIC + b"-1.7 rest of pdf data"
        attachment = Attachment(
            filename="document.pdf",
            content=content,
            mime_type="application/pdf",
        )
        assert attachment.content == content

    def test_valid_zip_content(self):
        """Test that valid ZIP content passes validation."""
        content = self.ZIP_MAGIC + b"rest of zip data"
        attachment = Attachment(
            filename="archive.zip",
            content=content,
            mime_type="application/zip",
        )
        assert attachment.content == content

    def test_valid_gzip_content(self):
        """Test that valid GZIP content passes validation."""
        content = self.GZIP_MAGIC + b"rest of gzip data"
        attachment = Attachment(
            filename="archive.gz",
            content=content,
            mime_type="application/gzip",
        )
        assert attachment.content == content

    def test_valid_bmp_content(self):
        """Test that valid BMP content passes validation."""
        content = self.BMP_MAGIC + b"rest of bmp data"
        attachment = Attachment(
            filename="image.bmp",
            content=content,
            mime_type="image/bmp",
        )
        assert attachment.content == content

    def test_valid_tiff_little_endian_content(self):
        """Test that valid TIFF (little-endian) content passes validation."""
        content = self.TIFF_LE_MAGIC + b"rest of tiff data"
        attachment = Attachment(
            filename="image.tiff",
            content=content,
            mime_type="image/tiff",
        )
        assert attachment.content == content

    def test_valid_tiff_big_endian_content(self):
        """Test that valid TIFF (big-endian) content passes validation."""
        content = self.TIFF_BE_MAGIC + b"rest of tiff data"
        attachment = Attachment(
            filename="image.tiff",
            content=content,
            mime_type="image/tiff",
        )
        assert attachment.content == content

    def test_valid_wav_content(self):
        """Test that valid WAV content passes validation."""
        content = self.RIFF_MAGIC + b"rest of wav data"
        attachment = Attachment(
            filename="audio.wav",
            content=content,
            mime_type="audio/wav",
        )
        assert attachment.content == content

    def test_valid_ogg_content(self):
        """Test that valid OGG content passes validation."""
        content = self.OGG_MAGIC + b"rest of ogg data"
        attachment = Attachment(
            filename="audio.ogg",
            content=content,
            mime_type="audio/ogg",
        )
        assert attachment.content == content

    def test_valid_mp3_with_id3_tag(self):
        """Test that valid MP3 with ID3 tag passes validation."""
        content = self.MP3_ID3_MAGIC + b"rest of mp3 data"
        attachment = Attachment(
            filename="audio.mp3",
            content=content,
            mime_type="audio/mpeg",
        )
        assert attachment.content == content

    def test_valid_mp3_with_sync_bytes(self):
        """Test that valid MP3 with sync bytes passes validation."""
        content = self.MP3_SYNC_MAGIC + b"rest of mp3 data"
        attachment = Attachment(
            filename="audio.mp3",
            content=content,
            mime_type="audio/mpeg",
        )
        assert attachment.content == content

    def test_invalid_png_content_raises_error(self):
        """Test that invalid PNG content raises ContentMismatchError."""
        content = b"not a png file"
        with pytest.raises(ContentMismatchError, match="does not match declared MIME type"):
            Attachment(
                filename="image.png",
                content=content,
                mime_type="image/png",
            )

    def test_invalid_jpeg_content_raises_error(self):
        """Test that invalid JPEG content raises ContentMismatchError."""
        content = b"not a jpeg file"
        with pytest.raises(ContentMismatchError, match="does not match declared MIME type"):
            Attachment(
                filename="image.jpg",
                content=content,
                mime_type="image/jpeg",
            )

    def test_invalid_pdf_content_raises_error(self):
        """Test that invalid PDF content raises ContentMismatchError."""
        content = b"not a pdf file"
        with pytest.raises(ContentMismatchError, match="does not match declared MIME type"):
            Attachment(
                filename="document.pdf",
                content=content,
                mime_type="application/pdf",
            )

    def test_invalid_zip_content_raises_error(self):
        """Test that invalid ZIP content raises ContentMismatchError."""
        content = b"not a zip file"
        with pytest.raises(ContentMismatchError, match="does not match declared MIME type"):
            Attachment(
                filename="archive.zip",
                content=content,
                mime_type="application/zip",
            )

    def test_content_mismatch_error_is_value_error(self):
        """Test that ContentMismatchError is a subclass of ValueError."""
        assert issubclass(ContentMismatchError, ValueError)
        content = b"not a png file"
        with pytest.raises(ValueError):
            Attachment(
                filename="image.png",
                content=content,
                mime_type="image/png",
            )

    def test_text_mime_types_skip_validation(self):
        """Test that text/* MIME types skip magic byte validation."""
        # Text content doesn't have reliable magic bytes
        content = b"Some plain text content"
        attachment = Attachment(
            filename="file.txt",
            content=content,
            mime_type="text/plain",
        )
        assert attachment.content == content

    def test_text_html_skips_validation(self):
        """Test that text/html skips magic byte validation."""
        content = b"<html><body>Hello</body></html>"
        attachment = Attachment(
            filename="page.html",
            content=content,
            mime_type="text/html",
        )
        assert attachment.content == content

    def test_application_json_skips_validation(self):
        """Test that application/json skips magic byte validation."""
        content = b'{"key": "value"}'
        attachment = Attachment(
            filename="data.json",
            content=content,
            mime_type="application/json",
        )
        assert attachment.content == content

    def test_application_xml_skips_validation(self):
        """Test that application/xml skips magic byte validation."""
        content = b"<root><item>value</item></root>"
        attachment = Attachment(
            filename="data.xml",
            content=content,
            mime_type="application/xml",
        )
        assert attachment.content == content

    def test_empty_content_skips_validation(self):
        """Test that empty content skips magic byte validation."""
        attachment = Attachment(
            filename="empty.png",
            content=b"",
            mime_type="image/png",
        )
        assert attachment.content == b""

    def test_validate_content_false_skips_validation(self):
        """Test that validate_content=False skips magic byte validation."""
        content = b"invalid png content"
        attachment = Attachment(
            filename="image.png",
            content=content,
            mime_type="image/png",
            validate_content=False,
        )
        assert attachment.content == content

    def test_validate_content_true_by_default(self):
        """Test that validate_content is True by default."""
        content = b"invalid png content"
        with pytest.raises(ContentMismatchError):
            Attachment(
                filename="image.png",
                content=content,
                mime_type="image/png",
            )

    def test_unknown_mime_type_skips_validation(self, caplog: pytest.LogCaptureFixture):
        """Test that unknown MIME types skip validation with debug log."""
        # Using a custom allowed MIME type that's not in MAGIC_BYTES
        custom_type = "application/x-custom-format"
        content = b"custom content"
        with caplog.at_level(logging.DEBUG):
            attachment = Attachment(
                filename="file.custom",
                content=content,
                mime_type=custom_type,
                allowed_mime_types=frozenset({custom_type}),
            )
        assert attachment.content == content

    def test_magic_bytes_dictionary_exists(self):
        """Test that MAGIC_BYTES dictionary is properly defined."""
        assert isinstance(MAGIC_BYTES, dict)
        assert "image/png" in MAGIC_BYTES
        assert "image/jpeg" in MAGIC_BYTES
        assert "application/pdf" in MAGIC_BYTES

    def test_error_message_contains_expected_magic_bytes(self):
        """Test that error message contains expected magic bytes info."""
        content = b"not a png"
        with pytest.raises(ContentMismatchError) as exc_info:
            Attachment(
                filename="image.png",
                content=content,
                mime_type="image/png",
            )
        error_msg = str(exc_info.value)
        assert "Expected magic bytes" in error_msg
        assert "image/png" in error_msg

    def test_error_message_contains_actual_content_preview(self):
        """Test that error message contains preview of actual content."""
        content = b"FAKEPNGDATA12345"
        with pytest.raises(ContentMismatchError) as exc_info:
            Attachment(
                filename="image.png",
                content=content,
                mime_type="image/png",
            )
        error_msg = str(exc_info.value)
        # The error should contain hex representation of the content
        assert "got:" in error_msg

    def test_office_document_docx_validation(self):
        """Test that .docx (ZIP-based) content is validated."""
        # DOCX files are ZIP archives
        content = self.ZIP_MAGIC + b"rest of docx data"
        attachment = Attachment(
            filename="document.docx",
            content=content,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert attachment.content == content

    def test_office_document_xlsx_validation(self):
        """Test that .xlsx (ZIP-based) content is validated."""
        # XLSX files are ZIP archives
        content = self.ZIP_MAGIC + b"rest of xlsx data"
        attachment = Attachment(
            filename="spreadsheet.xlsx",
            content=content,
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        assert attachment.content == content

    def test_office_document_pptx_validation(self):
        """Test that .pptx (ZIP-based) content is validated."""
        # PPTX files are ZIP archives
        content = self.ZIP_MAGIC + b"rest of pptx data"
        attachment = Attachment(
            filename="presentation.pptx",
            content=content,
            mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        assert attachment.content == content

    def test_webp_content_validation(self):
        """Test that WebP content is validated."""
        # WebP starts with RIFF
        content = self.RIFF_MAGIC + b"....WEBP rest of webp data"
        attachment = Attachment(
            filename="image.webp",
            content=content,
            mime_type="image/webp",
        )
        assert attachment.content == content

    def test_svg_with_xml_declaration(self):
        """Test that SVG with XML declaration passes validation."""
        content = b"<?xml version='1.0'?><svg>...</svg>"
        attachment = Attachment(
            filename="image.svg",
            content=content,
            mime_type="image/svg+xml",
        )
        assert attachment.content == content

    def test_svg_without_xml_declaration(self):
        """Test that SVG without XML declaration passes validation."""
        content = b"<svg xmlns='http://www.w3.org/2000/svg'>...</svg>"
        attachment = Attachment(
            filename="image.svg",
            content=content,
            mime_type="image/svg+xml",
        )
        assert attachment.content == content

    def test_combined_validation_with_other_checks(self):
        """Test that magic byte validation works with other validations."""
        # Test that all validations run: filename sanitization, size check,
        # MIME allowlist, and magic bytes
        content = self.PNG_MAGIC + b"png data"
        attachment = Attachment(
            filename="image.png",
            content=content,
            mime_type="image/png",
        )
        assert attachment.filename == "image.png"
        assert attachment.mime_type == "image/png"
        assert attachment.content == content
        assert attachment.validate_content is True

    @pytest.mark.parametrize(
        "mime_type,magic_bytes",
        [
            ("image/png", b"\x89PNG\r\n\x1a\n"),
            ("image/jpeg", b"\xff\xd8\xff"),
            ("image/gif", b"GIF89a"),
            ("application/pdf", b"%PDF"),
            ("application/zip", b"PK\x03\x04"),
            ("application/gzip", b"\x1f\x8b"),
            ("image/bmp", b"BM"),
            ("audio/ogg", b"OggS"),
        ],
    )
    def test_parametrized_valid_magic_bytes(self, mime_type: str, magic_bytes: bytes):
        """Test various MIME types with their correct magic bytes."""
        content = magic_bytes + b"rest of file data"
        attachment = Attachment(
            filename="file.bin",
            content=content,
            mime_type=mime_type,
        )
        assert attachment.content == content

    @pytest.mark.parametrize(
        "mime_type",
        [
            "image/png",
            "image/jpeg",
            "image/gif",
            "application/pdf",
            "application/zip",
        ],
    )
    def test_parametrized_invalid_content_raises_error(self, mime_type: str):
        """Test various MIME types with invalid content."""
        content = b"INVALID CONTENT THAT DOES NOT MATCH ANY MAGIC BYTES"
        with pytest.raises(ContentMismatchError):
            Attachment(
                filename="file.bin",
                content=content,
                mime_type=mime_type,
            )


# =============================================================================
# Attachment Drop Policy Tests
# =============================================================================


class TestAttachmentDropPolicy:
    """Tests for the attachment_drop_policy configuration option."""

    def test_default_policy_is_warn(self, test_app: Engine):
        """Test that the default policy is WARN for backward compatibility."""
        assert test_app.attachment_drop_policy == AttachmentDropPolicy.WARN

    def test_warn_policy_logs_warning_and_continues(
        self, test_app: Engine, caplog: pytest.LogCaptureFixture
    ):
        """Test that WARN policy logs a warning and still calls the notifier."""
        received_messages = []

        def legacy_notifier(message: str) -> None:
            received_messages.append(message)

        test_app.attachment_drop_policy = AttachmentDropPolicy.WARN
        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(legacy_notifier)

        with caplog.at_level(logging.WARNING):
            result = test_app.notify("test message", attachments=[attachment])

        # Notifier was called
        assert received_messages == ["test message"]
        # Warning was logged
        assert "does not support attachments" in caplog.text
        assert "1 attachment(s) will be dropped" in caplog.text
        # Result reflects dropped attachments
        assert result.notifiers_without_attachments == 1
        assert result.notifier_results[0].attachments_dropped == 1

    def test_error_policy_raises_exception(self, test_app: Engine):
        """Test that ERROR policy raises AttachmentDropError."""
        received_messages = []

        def legacy_notifier(message: str) -> None:
            received_messages.append(message)

        test_app.attachment_drop_policy = AttachmentDropPolicy.ERROR
        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(legacy_notifier)

        with pytest.raises(AttachmentDropError) as exc_info:
            test_app.notify("test message", attachments=[attachment])

        # Notifier was NOT called because exception was raised
        assert received_messages == []
        # Exception contains useful information
        assert exc_info.value.notifier_name == "legacy_notifier"
        assert exc_info.value.attachment_count == 1
        assert "does not support attachments" in str(exc_info.value)
        assert "1 attachment(s) would be dropped" in str(exc_info.value)

    def test_skip_notifier_policy_skips_legacy_notifier(
        self, test_app: Engine, caplog: pytest.LogCaptureFixture
    ):
        """Test that SKIP_NOTIFIER policy skips notifiers that don't support attachments."""
        legacy_messages = []
        modern_messages = []

        def legacy_notifier(message: str) -> None:
            legacy_messages.append(message)

        def modern_notifier(message: str, attachments: list[Attachment] | None = None) -> None:  # noqa: ARG001
            modern_messages.append(message)

        test_app.attachment_drop_policy = AttachmentDropPolicy.SKIP_NOTIFIER
        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(legacy_notifier)
        test_app.add_notifier(modern_notifier)

        with caplog.at_level(logging.WARNING):
            result = test_app.notify("test message", attachments=[attachment])

        # Legacy notifier was skipped, modern notifier was called
        assert legacy_messages == []
        assert modern_messages == ["test message"]
        # Warning was logged about skipping
        assert "Skipping notifier legacy_notifier" in caplog.text
        assert "does not support attachments" in caplog.text
        # Result reflects skipped notifier
        assert result.notifiers_skipped == 1
        assert result.notifiers_with_attachments == 1

    def test_policy_does_not_affect_notifiers_without_attachments(self, test_app: Engine):
        """Test that policy doesn't affect notifications without attachments."""
        received_messages = []

        def legacy_notifier(message: str) -> None:
            received_messages.append(message)

        # Even with ERROR policy, no exception if no attachments
        test_app.attachment_drop_policy = AttachmentDropPolicy.ERROR
        test_app.add_notifier(legacy_notifier)

        result = test_app.notify("test message")

        assert received_messages == ["test message"]
        assert result.total_notifiers == 1
        assert result.notifiers_skipped == 0

    def test_policy_does_not_affect_modern_notifiers(self, test_app: Engine):
        """Test that policy doesn't affect notifiers that support attachments."""
        received_attachments = []

        def modern_notifier(_message: str, attachments: list[Attachment] | None = None) -> None:
            received_attachments.append(attachments)

        test_app.attachment_drop_policy = AttachmentDropPolicy.ERROR
        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(modern_notifier)

        result = test_app.notify("test message", attachments=[attachment])

        assert len(received_attachments) == 1
        assert received_attachments[0] is not None
        assert result.notifiers_with_attachments == 1

    def test_error_policy_with_multiple_attachments(self, test_app: Engine):
        """Test that ERROR policy reports correct attachment count."""

        def legacy_notifier(_message: str) -> None:
            pass

        test_app.attachment_drop_policy = AttachmentDropPolicy.ERROR
        attachments = [
            Attachment(filename="file1.txt", content=b"one", mime_type="text/plain"),
            Attachment(filename="file2.txt", content=b"two", mime_type="text/plain"),
            Attachment(filename="file3.txt", content=b"three", mime_type="text/plain"),
        ]
        test_app.add_notifier(legacy_notifier)

        with pytest.raises(AttachmentDropError) as exc_info:
            test_app.notify("test", attachments=attachments)

        assert exc_info.value.attachment_count == 3
        assert "3 attachment(s) would be dropped" in str(exc_info.value)

    def test_notification_result_properties(self, test_app: Engine):
        """Test NotificationResult computed properties."""

        def legacy_notifier(_message: str) -> None:
            pass

        def modern_notifier(_message: str, attachments: list[Attachment] | None = None) -> None:  # noqa: ARG001
            pass

        test_app.attachment_drop_policy = AttachmentDropPolicy.WARN
        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(legacy_notifier)
        test_app.add_notifier(modern_notifier)

        result = test_app.notify("test", attachments=[attachment])

        assert result.total_notifiers == 2
        assert result.notifiers_with_attachments == 1
        assert result.notifiers_without_attachments == 1
        assert result.notifiers_skipped == 0

    def test_notification_result_with_skip_policy(self, test_app: Engine):
        """Test NotificationResult with SKIP_NOTIFIER policy."""

        def legacy_notifier(_message: str) -> None:
            pass

        def modern_notifier(_message: str, attachments: list[Attachment] | None = None) -> None:  # noqa: ARG001
            pass

        test_app.attachment_drop_policy = AttachmentDropPolicy.SKIP_NOTIFIER
        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(legacy_notifier)
        test_app.add_notifier(modern_notifier)

        result = test_app.notify("test", attachments=[attachment])

        assert result.total_notifiers == 2
        assert result.notifiers_with_attachments == 1
        assert result.notifiers_without_attachments == 0
        assert result.notifiers_skipped == 1

    def test_notifier_result_details(self, test_app: Engine):
        """Test that NotifierResult contains correct details."""

        def legacy_notifier(_message: str) -> None:
            pass

        def modern_notifier(_message: str, attachments: list[Attachment] | None = None) -> None:  # noqa: ARG001
            pass

        test_app.attachment_drop_policy = AttachmentDropPolicy.WARN
        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(legacy_notifier)
        test_app.add_notifier(modern_notifier)

        result = test_app.notify("test", attachments=[attachment])

        # Check legacy notifier result
        legacy_result = result.notifier_results[0]
        assert legacy_result.notifier_name == "legacy_notifier"
        assert legacy_result.received_attachments is False
        assert legacy_result.skipped is False
        assert legacy_result.attachments_dropped == 1

        # Check modern notifier result
        modern_result = result.notifier_results[1]
        assert modern_result.notifier_name == "modern_notifier"
        assert modern_result.received_attachments is True
        assert modern_result.skipped is False
        assert modern_result.attachments_dropped == 0

    def test_engine_constructor_accepts_policy(self):
        """Test that Engine constructor accepts attachment_drop_policy parameter."""
        from platzky.config import Config
        from platzky.db.json_db import Json

        config_data = {
            "APP_NAME": "testApp",
            "SECRET_KEY": "secret",
            "BLOG_PREFIX": "/blog",
            "TRANSLATION_DIRECTORIES": [],
            "DB": {"TYPE": "json", "DATA": {"site_content": {"pages": []}}},
        }
        config = Config.model_validate(config_data)
        db = Json(config.db)

        engine = Engine(
            config, db, "test", attachment_drop_policy=AttachmentDropPolicy.ERROR
        )

        assert engine.attachment_drop_policy == AttachmentDropPolicy.ERROR

    def test_all_policy_values(self):
        """Test that all policy values are defined."""
        assert AttachmentDropPolicy.WARN.value == "warn"
        assert AttachmentDropPolicy.ERROR.value == "error"
        assert AttachmentDropPolicy.SKIP_NOTIFIER.value == "skip_notifier"

    def test_attachment_drop_error_attributes(self):
        """Test AttachmentDropError has correct attributes."""
        error = AttachmentDropError("test_notifier", 5)

        assert error.notifier_name == "test_notifier"
        assert error.attachment_count == 5
        assert "test_notifier" in str(error)
        assert "5 attachment(s)" in str(error)

    def test_mixed_notifiers_with_error_policy_fails_on_first_legacy(self, test_app: Engine):
        """Test that ERROR policy fails on the first legacy notifier encountered."""
        modern_messages = []
        legacy_messages = []

        def modern_notifier(message: str, attachments: list[Attachment] | None = None) -> None:  # noqa: ARG001
            modern_messages.append(message)

        def legacy_notifier(message: str) -> None:
            legacy_messages.append(message)

        test_app.attachment_drop_policy = AttachmentDropPolicy.ERROR
        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        # Add modern first, then legacy
        test_app.add_notifier(modern_notifier)
        test_app.add_notifier(legacy_notifier)

        with pytest.raises(AttachmentDropError):
            test_app.notify("test", attachments=[attachment])

        # Modern notifier was called before encountering legacy
        assert modern_messages == ["test"]
        # Legacy notifier was not called
        assert legacy_messages == []

    def test_notification_result_empty_list(self, test_app: Engine):
        """Test NotificationResult with no notifiers."""
        result = test_app.notify("test")

        assert result.total_notifiers == 0
        assert result.notifiers_with_attachments == 0
        assert result.notifiers_without_attachments == 0
        assert result.notifiers_skipped == 0

    def test_notify_returns_result_even_without_attachments(self, test_app: Engine):
        """Test that notify returns NotificationResult even when no attachments."""

        def notifier(_message: str) -> None:
            pass

        test_app.add_notifier(notifier)
        result = test_app.notify("test")

        assert isinstance(result, NotificationResult)
        assert result.total_notifiers == 1
        assert result.notifier_results[0].notifier_name == "notifier"
