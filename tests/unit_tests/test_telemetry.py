import sys
from unittest.mock import MagicMock

import pytest

from platzky.config import TelemetryConfig


# Mock OpenTelemetry modules before importing telemetry
@pytest.fixture(autouse=True)
def mock_opentelemetry_modules():
    """Mock OpenTelemetry modules for testing"""
    mock_modules = {
        "opentelemetry": MagicMock(),
        "opentelemetry.trace": MagicMock(),
        "opentelemetry.instrumentation": MagicMock(),
        "opentelemetry.instrumentation.flask": MagicMock(),
        "opentelemetry.sdk": MagicMock(),
        "opentelemetry.sdk.resources": MagicMock(),
        "opentelemetry.sdk.trace": MagicMock(),
        "opentelemetry.sdk.trace.export": MagicMock(),
        "opentelemetry.exporter": MagicMock(),
        "opentelemetry.exporter.otlp": MagicMock(),
        "opentelemetry.exporter.otlp.proto": MagicMock(),
        "opentelemetry.exporter.otlp.proto.grpc": MagicMock(),
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": MagicMock(),
        "opentelemetry.semconv": MagicMock(),
        "opentelemetry.semconv.resource": MagicMock(),
    }

    for module_name, mock_module in mock_modules.items():
        sys.modules[module_name] = mock_module

    # Force reimport of telemetry module
    if "platzky.telemetry" in sys.modules:
        del sys.modules["platzky.telemetry"]
    if "platzky.config" in sys.modules:
        del sys.modules["platzky.config"]

    # Import setup_telemetry after mocking
    import importlib

    import platzky.telemetry

    importlib.reload(platzky.telemetry)

    yield platzky.telemetry.setup_telemetry

    # Cleanup
    for module_name in mock_modules:
        if module_name in sys.modules:
            del sys.modules[module_name]


@pytest.fixture
def mock_app():
    """Create a mock Flask app for testing"""
    app = MagicMock()
    app.config = {"APP_NAME": "test-app"}
    return app


def test_telemetry_disabled(mock_opentelemetry_modules):
    """Test that telemetry setup returns None when disabled"""
    app = MagicMock()
    config = TelemetryConfig(enabled=False)

    result = mock_opentelemetry_modules(app, config)

    assert result is None


def test_telemetry_console_exporter(mock_opentelemetry_modules, mock_app):
    """Test telemetry setup with console exporter"""
    config = TelemetryConfig(enabled=True, console_export=True)

    result = mock_opentelemetry_modules(mock_app, config)

    assert result is not None


def test_telemetry_otlp_exporter(mock_opentelemetry_modules, mock_app):
    """Test telemetry setup with OTLP exporter"""
    config = TelemetryConfig(enabled=True, endpoint="http://localhost:4317")

    result = mock_opentelemetry_modules(mock_app, config)

    assert result is not None


def test_telemetry_gcp_trace_exporter(mock_opentelemetry_modules, mock_app):
    """Test telemetry setup with GCP Trace exporter"""
    config = TelemetryConfig(enabled=True, endpoint="https://telemetry.googleapis.com")

    result = mock_opentelemetry_modules(mock_app, config)

    assert result is not None


def test_telemetry_console_export_with_other_exporter(mock_opentelemetry_modules, mock_app):
    """Test that console_export adds console exporter alongside main exporter"""
    config = TelemetryConfig(enabled=True, endpoint="http://localhost:4317", console_export=True)

    result = mock_opentelemetry_modules(mock_app, config)

    assert result is not None


def test_telemetry_config_defaults():
    """Test TelemetryConfig default values"""
    config = TelemetryConfig()

    assert config.enabled is False
    assert config.endpoint is None
    assert config.console_export is False


def test_telemetry_config_custom_values():
    """Test TelemetryConfig with custom values"""
    config = TelemetryConfig(enabled=True, endpoint="https://custom:4317", console_export=True)

    assert config.enabled is True
    assert config.endpoint == "https://custom:4317"
    assert config.console_export is True


def test_telemetry_deployment_environment(mock_opentelemetry_modules, mock_app):
    """Test telemetry setup with deployment_environment"""
    config = TelemetryConfig(
        enabled=True, endpoint="http://localhost:4317", deployment_environment="production"
    )

    result = mock_opentelemetry_modules(mock_app, config)

    assert result is not None


def test_telemetry_service_instance_id(mock_opentelemetry_modules, mock_app):
    """Test telemetry setup with custom service_instance_id"""
    config = TelemetryConfig(
        enabled=True, endpoint="http://localhost:4317", service_instance_id="custom-instance-123"
    )

    result = mock_opentelemetry_modules(mock_app, config)

    assert result is not None


def test_telemetry_import_error(monkeypatch):
    """Test that ImportError is raised when OpenTelemetry is not available"""
    # Mock the module to simulate OpenTelemetry not being available
    import platzky.telemetry

    monkeypatch.setattr(platzky.telemetry, "_otel_available", False)

    app = MagicMock()
    config = TelemetryConfig(enabled=True)

    with pytest.raises(ImportError, match="OpenTelemetry is not installed"):
        platzky.telemetry.setup_telemetry(app, config)


def test_telemetry_version_not_available(mock_opentelemetry_modules, mock_app, monkeypatch):
    """Test telemetry setup when package version is not available"""

    def mock_get_version(package):
        raise Exception("Version not found")

    # Mock importlib.metadata.version to raise an exception
    monkeypatch.setattr("importlib.metadata.version", mock_get_version)
    monkeypatch.setattr("platzky.telemetry.get_version", mock_get_version)

    config = TelemetryConfig(enabled=True, endpoint="http://localhost:4317")

    # Should not raise an exception, just skip version
    result = mock_opentelemetry_modules(mock_app, config)

    assert result is not None
