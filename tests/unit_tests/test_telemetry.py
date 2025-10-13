"""Telemetry tests using real OpenTelemetry library.

These tests use the actual OpenTelemetry packages instead of mocks,
providing integration-level testing with better coverage.
"""

from unittest.mock import MagicMock

import pytest

from platzky.config import TelemetryConfig
from platzky.telemetry import setup_telemetry


@pytest.fixture
def mock_app():
    """Create a mock Flask app for testing."""
    app = MagicMock()
    app.config = {"APP_NAME": "test-app"}
    return app


def test_telemetry_disabled(mock_app):
    """Test that telemetry setup returns None when disabled."""
    config = TelemetryConfig(enabled=False)

    result = setup_telemetry(mock_app, config)

    assert result is None


def test_telemetry_console_exporter(mock_app):
    """Test telemetry setup with console exporter."""
    config = TelemetryConfig(enabled=True, console_export=True)

    tracer = setup_telemetry(mock_app, config)

    # Verify tracer was returned
    assert tracer is not None

    # Verify we can create and use spans
    with tracer.start_as_current_span("test_span") as span:
        assert span is not None
        assert span.is_recording()


def test_telemetry_otlp_exporter(mock_app):
    """Test telemetry setup with OTLP exporter."""
    config = TelemetryConfig(enabled=True, endpoint="http://localhost:4317")

    tracer = setup_telemetry(mock_app, config)

    # Verify tracer was returned
    assert tracer is not None

    # Verify we can create and use spans
    with tracer.start_as_current_span("test_span") as span:
        assert span is not None
        assert span.is_recording()


def test_telemetry_gcp_trace_exporter(mock_app):
    """Test telemetry setup with GCP Trace exporter."""
    config = TelemetryConfig(enabled=True, endpoint="https://telemetry.googleapis.com")

    tracer = setup_telemetry(mock_app, config)

    # Verify tracer was returned
    assert tracer is not None

    # Verify we can create and use spans
    with tracer.start_as_current_span("test_span") as span:
        assert span is not None
        assert span.is_recording()


def test_telemetry_console_export_with_other_exporter(mock_app):
    """Test that console_export adds console exporter alongside main exporter."""
    config = TelemetryConfig(enabled=True, endpoint="http://localhost:4317", console_export=True)

    tracer = setup_telemetry(mock_app, config)

    # Verify tracer was returned
    assert tracer is not None

    # Verify we can create and use spans
    with tracer.start_as_current_span("test_span") as span:
        assert span is not None
        assert span.is_recording()


def test_telemetry_config_defaults():
    """Test TelemetryConfig default values."""
    config = TelemetryConfig()

    assert config.enabled is False
    assert config.endpoint is None
    assert config.console_export is False
    assert config.timeout == 10
    assert config.deployment_environment is None
    assert config.service_instance_id is None


def test_telemetry_config_custom_values():
    """Test TelemetryConfig with custom values."""
    config = TelemetryConfig(
        enabled=True,
        endpoint="https://custom:4317",
        console_export=True,
        timeout=30,
        deployment_environment="production",
        service_instance_id="custom-id",
    )

    assert config.enabled is True
    assert config.endpoint == "https://custom:4317"
    assert config.console_export is True
    assert config.timeout == 30
    assert config.deployment_environment == "production"
    assert config.service_instance_id == "custom-id"


@pytest.mark.parametrize(
    ("invalid_endpoint", "error_match"),
    [
        ("localhost:4317", "Invalid endpoint.*Must be http"),  # no scheme
        ("ftp://localhost:4317", "Invalid endpoint.*Must be http"),  # bad scheme
        ("https://", "Invalid endpoint.*Must be http"),  # malformed
        ("https://:4317", "Invalid endpoint.*Must be http"),  # no hostname
    ],
    ids=["no_scheme", "bad_scheme", "malformed", "no_hostname"],
)
def test_telemetry_config_invalid_endpoint(invalid_endpoint, error_match):
    """Test TelemetryConfig rejects invalid endpoint formats."""
    with pytest.raises(ValueError, match=error_match):
        TelemetryConfig(enabled=True, endpoint=invalid_endpoint)


@pytest.mark.parametrize(
    "invalid_timeout",
    [0, -1, -10],
    ids=["zero", "negative_one", "negative_ten"],
)
def test_telemetry_config_invalid_timeout(invalid_timeout):
    """Test TelemetryConfig rejects non-positive timeout values."""
    with pytest.raises(ValueError, match="greater than 0"):
        TelemetryConfig(enabled=True, timeout=invalid_timeout)


def test_telemetry_enabled_without_exporters(mock_app):
    """Test telemetry with enabled=True but no exporters raises ValueError."""
    config = TelemetryConfig(enabled=True, endpoint=None, console_export=False)

    with pytest.raises(ValueError, match="no exporters are configured"):
        setup_telemetry(mock_app, config)


def test_telemetry_deployment_environment(mock_app):
    """Test telemetry setup with deployment_environment."""
    config = TelemetryConfig(enabled=True, console_export=True, deployment_environment="production")

    tracer = setup_telemetry(mock_app, config)

    # Verify tracer was returned and is functional
    assert tracer is not None
    with tracer.start_as_current_span("test_span") as span:
        assert span.is_recording()


def test_telemetry_service_instance_id_custom(mock_app):
    """Test telemetry setup with custom service_instance_id."""
    config = TelemetryConfig(
        enabled=True, console_export=True, service_instance_id="custom-instance-123"
    )

    tracer = setup_telemetry(mock_app, config)

    # Verify tracer was returned and is functional
    assert tracer is not None
    with tracer.start_as_current_span("test_span") as span:
        assert span.is_recording()


def test_telemetry_service_instance_id_auto_generated(mock_app, monkeypatch):
    """Test telemetry setup with auto-generated service_instance_id."""
    # Mock hostname and UUID for predictable testing
    monkeypatch.setattr("socket.gethostname", lambda: "test-host")

    import uuid

    def mock_uuid4() -> object:
        class MockUUID:
            def __str__(self) -> str:
                return "12345678-abcd-efgh-ijkl-mnopqrstuvwx"

        return MockUUID()

    monkeypatch.setattr(uuid, "uuid4", mock_uuid4)

    config = TelemetryConfig(enabled=True, console_export=True)

    tracer = setup_telemetry(mock_app, config)

    # Verify tracer was returned and is functional
    assert tracer is not None
    with tracer.start_as_current_span("test_span") as span:
        assert span.is_recording()


def test_telemetry_version_not_available(mock_app, monkeypatch):
    """Test telemetry setup when package version is not available."""
    # Patch importlib.metadata.version to raise PackageNotFoundError
    from importlib.metadata import PackageNotFoundError

    def mock_version(_package_name: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr("importlib.metadata.version", mock_version)

    config = TelemetryConfig(enabled=True, console_export=True)

    tracer = setup_telemetry(mock_app, config)

    # Verify we don't crash when version is unavailable and tracer is functional
    assert tracer is not None
    with tracer.start_as_current_span("test_span") as span:
        assert span.is_recording()


def test_telemetry_service_name_from_app_config(mock_app):
    """Test that service name is taken from Flask app config."""
    mock_app.config = {"APP_NAME": "my-custom-app"}

    config = TelemetryConfig(enabled=True, console_export=True)

    tracer = setup_telemetry(mock_app, config)

    # Verify tracer was returned and is functional
    assert tracer is not None
    with tracer.start_as_current_span("test_span") as span:
        assert span.is_recording()


def test_telemetry_can_create_spans(mock_app):
    """Test that we can actually create spans after setup."""
    config = TelemetryConfig(enabled=True, console_export=True)

    tracer = setup_telemetry(mock_app, config)

    assert tracer is not None

    # Create a test span
    with tracer.start_as_current_span("test_operation") as span:
        assert span is not None
        assert span.is_recording()

        # Add some attributes
        span.set_attribute("test.attribute", "test_value")
        span.add_event("test_event")

    # Span should be ended
    assert not span.is_recording()
