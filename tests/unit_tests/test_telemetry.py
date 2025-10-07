import sys
from unittest.mock import MagicMock

import pytest

from platzky.config import TelemetryConfig


# Mock OpenTelemetry modules before importing telemetry
@pytest.fixture(autouse=True)
def mock_opentelemetry_modules():
    """Mock OpenTelemetry modules for testing"""
    # Save original module state for restoration
    original_telemetry = sys.modules.get("platzky.telemetry")
    original_config = sys.modules.get("platzky.config")

    # Create specific mock instances to track
    mock_tracer = MagicMock()
    mock_tracer_provider = MagicMock()
    mock_resource = MagicMock()
    mock_flask_instrumentor_instance = MagicMock()
    mock_otlp_exporter = MagicMock()
    mock_console_exporter = MagicMock()
    mock_batch_span_processor = MagicMock()

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

    # Configure mocks with return values
    mock_modules["opentelemetry.trace"].get_tracer.return_value = mock_tracer
    mock_modules["opentelemetry.sdk.trace"].TracerProvider.return_value = mock_tracer_provider
    mock_modules["opentelemetry.sdk.resources"].Resource.create.return_value = mock_resource
    mock_modules["opentelemetry.instrumentation.flask"].FlaskInstrumentor.return_value = (
        mock_flask_instrumentor_instance
    )
    mock_modules[
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter"
    ].OTLPSpanExporter.return_value = mock_otlp_exporter
    mock_modules["opentelemetry.sdk.trace.export"].ConsoleSpanExporter.return_value = (
        mock_console_exporter
    )
    mock_modules["opentelemetry.sdk.trace.export"].BatchSpanProcessor.return_value = (
        mock_batch_span_processor
    )

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

    # Return mocks for assertions
    yield {
        "setup_telemetry": platzky.telemetry.setup_telemetry,
        "TracerProvider": mock_modules["opentelemetry.sdk.trace"].TracerProvider,
        "Resource": mock_modules["opentelemetry.sdk.resources"].Resource,
        "FlaskInstrumentor": mock_modules["opentelemetry.instrumentation.flask"].FlaskInstrumentor,
        "OTLPSpanExporter": mock_modules[
            "opentelemetry.exporter.otlp.proto.grpc.trace_exporter"
        ].OTLPSpanExporter,
        "ConsoleSpanExporter": mock_modules["opentelemetry.sdk.trace.export"].ConsoleSpanExporter,
        "BatchSpanProcessor": mock_modules["opentelemetry.sdk.trace.export"].BatchSpanProcessor,
        "set_tracer_provider": mock_modules["opentelemetry.trace"].set_tracer_provider,
        "tracer_provider": mock_tracer_provider,
        "flask_instrumentor": mock_flask_instrumentor_instance,
    }

    # Cleanup: remove mocked modules
    for module_name in mock_modules:
        if module_name in sys.modules:
            del sys.modules[module_name]

    # Restore original platzky modules
    if "platzky.telemetry" in sys.modules:
        del sys.modules["platzky.telemetry"]
    if "platzky.config" in sys.modules:
        del sys.modules["platzky.config"]

    if original_telemetry is not None:
        sys.modules["platzky.telemetry"] = original_telemetry
    if original_config is not None:
        sys.modules["platzky.config"] = original_config


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

    result = mock_opentelemetry_modules["setup_telemetry"](app, config)

    assert result is None
    # Verify no OpenTelemetry components were initialized
    mock_opentelemetry_modules["TracerProvider"].assert_not_called()
    mock_opentelemetry_modules["FlaskInstrumentor"].assert_not_called()


def test_telemetry_console_exporter(mock_opentelemetry_modules, mock_app):
    """Test telemetry setup with console exporter"""
    config = TelemetryConfig(enabled=True, console_export=True)

    result = mock_opentelemetry_modules["setup_telemetry"](mock_app, config)

    assert result is not None

    # Verify Resource was created with service.name
    mock_opentelemetry_modules["Resource"].create.assert_called_once()
    resource_attrs = mock_opentelemetry_modules["Resource"].create.call_args[0][0]
    # Check that resource_attrs dict contains test-app value
    assert "test-app" in resource_attrs.values()

    # Verify TracerProvider was created with the resource
    mock_opentelemetry_modules["TracerProvider"].assert_called_once()

    # Verify ConsoleSpanExporter was created
    mock_opentelemetry_modules["ConsoleSpanExporter"].assert_called_once()

    # Verify BatchSpanProcessor was called once (for console exporter only)
    assert mock_opentelemetry_modules["BatchSpanProcessor"].call_count == 1

    # Verify add_span_processor was called once
    mock_opentelemetry_modules["tracer_provider"].add_span_processor.assert_called_once()

    # Verify FlaskInstrumentor was used
    mock_opentelemetry_modules["FlaskInstrumentor"].assert_called_once()
    mock_opentelemetry_modules["flask_instrumentor"].instrument_app.assert_called_once_with(
        mock_app
    )


def test_telemetry_otlp_exporter(mock_opentelemetry_modules, mock_app):
    """Test telemetry setup with OTLP exporter"""
    config = TelemetryConfig(enabled=True, endpoint="https://localhost:4317")

    result = mock_opentelemetry_modules["setup_telemetry"](mock_app, config)

    assert result is not None

    # Verify OTLPSpanExporter was created with correct endpoint
    mock_opentelemetry_modules["OTLPSpanExporter"].assert_called_once_with(
        endpoint="https://localhost:4317", timeout=10
    )

    # Verify BatchSpanProcessor was called once (for OTLP exporter only)
    assert mock_opentelemetry_modules["BatchSpanProcessor"].call_count == 1

    # Verify add_span_processor was called once
    mock_opentelemetry_modules["tracer_provider"].add_span_processor.assert_called_once()

    # Verify FlaskInstrumentor was used
    mock_opentelemetry_modules["flask_instrumentor"].instrument_app.assert_called_once_with(
        mock_app
    )


def test_telemetry_gcp_trace_exporter(mock_opentelemetry_modules, mock_app):
    """Test telemetry setup with GCP Trace exporter"""
    config = TelemetryConfig(enabled=True, endpoint="https://telemetry.googleapis.com")

    result = mock_opentelemetry_modules["setup_telemetry"](mock_app, config)

    assert result is not None

    # Verify OTLPSpanExporter was created with GCP endpoint
    mock_opentelemetry_modules["OTLPSpanExporter"].assert_called_once_with(
        endpoint="https://telemetry.googleapis.com", timeout=10
    )

    # Verify BatchSpanProcessor was called once
    assert mock_opentelemetry_modules["BatchSpanProcessor"].call_count == 1

    # Verify add_span_processor was called once
    mock_opentelemetry_modules["tracer_provider"].add_span_processor.assert_called_once()


def test_telemetry_console_export_with_other_exporter(mock_opentelemetry_modules, mock_app):
    """Test that console_export adds console exporter alongside main exporter"""
    config = TelemetryConfig(enabled=True, endpoint="https://localhost:4317", console_export=True)

    result = mock_opentelemetry_modules["setup_telemetry"](mock_app, config)

    assert result is not None

    # Verify OTLPSpanExporter was created
    mock_opentelemetry_modules["OTLPSpanExporter"].assert_called_once_with(
        endpoint="https://localhost:4317", timeout=10
    )

    # Verify ConsoleSpanExporter was also created
    mock_opentelemetry_modules["ConsoleSpanExporter"].assert_called_once()

    # Verify BatchSpanProcessor was called twice (once for OTLP, once for Console)
    assert mock_opentelemetry_modules["BatchSpanProcessor"].call_count == 2

    # Verify add_span_processor was called twice
    assert mock_opentelemetry_modules["tracer_provider"].add_span_processor.call_count == 2


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
        enabled=True, endpoint="https://localhost:4317", deployment_environment="production"
    )

    result = mock_opentelemetry_modules["setup_telemetry"](mock_app, config)

    assert result is not None

    # Verify Resource was created with deployment.environment
    resource_attrs = mock_opentelemetry_modules["Resource"].create.call_args[0][0]
    assert "production" in resource_attrs.values()


def test_telemetry_service_instance_id(mock_opentelemetry_modules, mock_app):
    """Test telemetry setup with custom service_instance_id"""
    config = TelemetryConfig(
        enabled=True,
        endpoint="https://localhost:4317",
        service_instance_id="custom-instance-123",
    )

    result = mock_opentelemetry_modules["setup_telemetry"](mock_app, config)

    assert result is not None

    # Verify Resource was created with service.instance.id
    resource_attrs = mock_opentelemetry_modules["Resource"].create.call_args[0][0]
    assert "custom-instance-123" in resource_attrs.values()


def test_telemetry_import_error(mock_app, monkeypatch):
    """Test that ImportError is raised when OpenTelemetry is not available"""
    # Mock the module to simulate OpenTelemetry not being available
    import platzky.telemetry

    monkeypatch.setattr(platzky.telemetry, "_otel_available", False)

    config = TelemetryConfig(enabled=True)

    with pytest.raises(ImportError, match="OpenTelemetry is not installed"):
        platzky.telemetry.setup_telemetry(mock_app, config)


def test_telemetry_version_not_available(mock_opentelemetry_modules, mock_app, monkeypatch):
    """Test telemetry setup when package version is not available"""
    # Mock the version function to raise an exception
    mock_metadata = MagicMock()
    mock_metadata.version.side_effect = Exception("Version not found")
    monkeypatch.setitem(sys.modules, "importlib.metadata", mock_metadata)

    # Force reimport to pick up the mocked metadata
    if "platzky.telemetry" in sys.modules:
        del sys.modules["platzky.telemetry"]

    import importlib

    import platzky.telemetry

    importlib.reload(platzky.telemetry)

    config = TelemetryConfig(enabled=True, endpoint="https://localhost:4317")
    result = platzky.telemetry.setup_telemetry(mock_app, config)

    assert result is not None

    # Verify Resource was created - version will be missing or be a mock
    # Just verify that setup completed without error
    mock_opentelemetry_modules["Resource"].create.assert_called()
