import sys
from unittest.mock import MagicMock

import pytest

from platzky.config import TelemetryConfig


# Mock OpenTelemetry modules before importing telemetry
@pytest.fixture(autouse=True)
def mock_opentelemetry_modules(request):
    """Mock OpenTelemetry modules for testing"""
    # Allow tests to opt out of autouse
    if "no_mock_otel" in request.keywords:
        yield None
        return

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

    # Create mock modules structure
    mock_trace_module = MagicMock()
    mock_modules = {
        "opentelemetry": MagicMock(),
        "opentelemetry.trace": mock_trace_module,
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

    # Link trace module to parent opentelemetry module
    mock_modules["opentelemetry"].trace = mock_trace_module

    # Create mock constants for resource attributes
    mock_service_name = MagicMock()
    mock_service_version = MagicMock()
    mock_deployment_env = MagicMock()
    mock_instance_id = MagicMock()

    # Configure resource attribute mocks
    mock_modules["opentelemetry.semconv.resource"].ResourceAttributes.SERVICE_NAME = (
        mock_service_name
    )
    mock_modules["opentelemetry.semconv.resource"].ResourceAttributes.SERVICE_VERSION = (
        mock_service_version
    )
    mock_modules["opentelemetry.semconv.resource"].ResourceAttributes.DEPLOYMENT_ENVIRONMENT = (
        mock_deployment_env
    )
    mock_modules["opentelemetry.semconv.resource"].ResourceAttributes.SERVICE_INSTANCE_ID = (
        mock_instance_id
    )

    # Configure mocks with return values
    mock_trace_module.get_tracer.return_value = mock_tracer
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
        "trace_module": mock_trace_module,
        "tracer_provider": mock_tracer_provider,
        "flask_instrumentor": mock_flask_instrumentor_instance,
        "tracer": mock_tracer,
        "resource": mock_resource,
        "otlp_exporter": mock_otlp_exporter,
        "console_exporter": mock_console_exporter,
        "batch_span_processor": mock_batch_span_processor,
        "SERVICE_NAME": mock_service_name,
        "SERVICE_VERSION": mock_service_version,
        "DEPLOYMENT_ENVIRONMENT": mock_deployment_env,
        "SERVICE_INSTANCE_ID": mock_instance_id,
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

    # Verify tracer was returned (get_tracer was called)
    assert result is not None

    # Verify Resource was created with service.name key-value pair
    mock_opentelemetry_modules["Resource"].create.assert_called_once()
    resource_attrs = mock_opentelemetry_modules["Resource"].create.call_args[0][0]
    assert mock_opentelemetry_modules["SERVICE_NAME"] in resource_attrs
    assert resource_attrs[mock_opentelemetry_modules["SERVICE_NAME"]] == "test-app"

    # Verify TracerProvider was created with the resource
    mock_opentelemetry_modules["TracerProvider"].assert_called_once_with(
        resource=mock_opentelemetry_modules["resource"]
    )

    # Verify ConsoleSpanExporter was created
    mock_opentelemetry_modules["ConsoleSpanExporter"].assert_called_once()

    # Verify BatchSpanProcessor was called with console exporter
    mock_opentelemetry_modules["BatchSpanProcessor"].assert_called_once_with(
        mock_opentelemetry_modules["console_exporter"]
    )

    # Verify add_span_processor was called with the processor
    mock_opentelemetry_modules["tracer_provider"].add_span_processor.assert_called_once_with(
        mock_opentelemetry_modules["batch_span_processor"]
    )

    # Verify set_tracer_provider was called with the provider
    mock_opentelemetry_modules["trace_module"].set_tracer_provider.assert_called_once_with(
        mock_opentelemetry_modules["tracer_provider"]
    )

    # Verify FlaskInstrumentor was used
    mock_opentelemetry_modules["FlaskInstrumentor"].assert_called_once()
    mock_opentelemetry_modules["flask_instrumentor"].instrument_app.assert_called_once_with(
        mock_app
    )


def test_telemetry_otlp_exporter(mock_opentelemetry_modules, mock_app):
    """Test telemetry setup with OTLP exporter"""
    config = TelemetryConfig(enabled=True, endpoint="https://localhost:4317")

    result = mock_opentelemetry_modules["setup_telemetry"](mock_app, config)

    # Verify tracer was returned (get_tracer was called)
    assert result is not None

    # Verify OTLPSpanExporter was created with correct endpoint
    mock_opentelemetry_modules["OTLPSpanExporter"].assert_called_once_with(
        endpoint="https://localhost:4317", timeout=10
    )

    # Verify BatchSpanProcessor was called with OTLP exporter
    mock_opentelemetry_modules["BatchSpanProcessor"].assert_called_once_with(
        mock_opentelemetry_modules["otlp_exporter"]
    )

    # Verify TracerProvider was called with resource
    mock_opentelemetry_modules["TracerProvider"].assert_called_once_with(
        resource=mock_opentelemetry_modules["resource"]
    )

    # Verify add_span_processor was called with processor
    mock_opentelemetry_modules["tracer_provider"].add_span_processor.assert_called_once_with(
        mock_opentelemetry_modules["batch_span_processor"]
    )

    # Verify set_tracer_provider was called with the provider
    mock_opentelemetry_modules["trace_module"].set_tracer_provider.assert_called_once_with(
        mock_opentelemetry_modules["tracer_provider"]
    )

    # Verify FlaskInstrumentor was used
    mock_opentelemetry_modules["flask_instrumentor"].instrument_app.assert_called_once_with(
        mock_app
    )


def test_telemetry_gcp_trace_exporter(mock_opentelemetry_modules, mock_app):
    """Test telemetry setup with GCP Trace exporter"""
    config = TelemetryConfig(enabled=True, endpoint="https://telemetry.googleapis.com")

    result = mock_opentelemetry_modules["setup_telemetry"](mock_app, config)

    # Verify tracer was returned (get_tracer was called)
    assert result is not None

    # Verify OTLPSpanExporter was created with GCP endpoint
    mock_opentelemetry_modules["OTLPSpanExporter"].assert_called_once_with(
        endpoint="https://telemetry.googleapis.com", timeout=10
    )

    # Verify BatchSpanProcessor was called with OTLP exporter
    mock_opentelemetry_modules["BatchSpanProcessor"].assert_called_once_with(
        mock_opentelemetry_modules["otlp_exporter"]
    )

    # Verify add_span_processor was called with processor
    mock_opentelemetry_modules["tracer_provider"].add_span_processor.assert_called_once_with(
        mock_opentelemetry_modules["batch_span_processor"]
    )

    # Verify set_tracer_provider was called with the provider
    mock_opentelemetry_modules["trace_module"].set_tracer_provider.assert_called_once_with(
        mock_opentelemetry_modules["tracer_provider"]
    )


def test_telemetry_console_export_with_other_exporter(mock_opentelemetry_modules, mock_app):
    """Test that console_export adds console exporter alongside main exporter"""
    config = TelemetryConfig(enabled=True, endpoint="https://localhost:4317", console_export=True)

    result = mock_opentelemetry_modules["setup_telemetry"](mock_app, config)

    # Verify tracer was returned (get_tracer was called)
    assert result is not None

    # Verify OTLPSpanExporter was created
    mock_opentelemetry_modules["OTLPSpanExporter"].assert_called_once_with(
        endpoint="https://localhost:4317", timeout=10
    )

    # Verify ConsoleSpanExporter was also created
    mock_opentelemetry_modules["ConsoleSpanExporter"].assert_called_once()

    # Verify BatchSpanProcessor was called twice with correct exporters
    assert mock_opentelemetry_modules["BatchSpanProcessor"].call_count == 2
    calls = mock_opentelemetry_modules["BatchSpanProcessor"].call_args_list
    # First call with OTLP exporter, second with console exporter
    assert calls[0][0][0] == mock_opentelemetry_modules["otlp_exporter"]
    assert calls[1][0][0] == mock_opentelemetry_modules["console_exporter"]

    # Verify add_span_processor was called twice
    assert mock_opentelemetry_modules["tracer_provider"].add_span_processor.call_count == 2

    # Verify set_tracer_provider was called with the provider
    mock_opentelemetry_modules["trace_module"].set_tracer_provider.assert_called_once_with(
        mock_opentelemetry_modules["tracer_provider"]
    )


def test_telemetry_config_defaults():
    """Test TelemetryConfig default values"""
    config = TelemetryConfig()

    assert config.enabled is False
    assert config.endpoint is None
    assert config.console_export is False
    assert config.timeout == 10


def test_telemetry_config_custom_values():
    """Test TelemetryConfig with custom values"""
    config = TelemetryConfig(enabled=True, endpoint="https://custom:4317", console_export=True)

    assert config.enabled is True
    assert config.endpoint == "https://custom:4317"
    assert config.console_export is True


def test_telemetry_config_invalid_endpoint_no_scheme():
    """Test TelemetryConfig rejects endpoint without scheme"""
    with pytest.raises(ValueError, match="Invalid endpoint.*Must be http"):
        TelemetryConfig(enabled=True, endpoint="localhost:4317")


def test_telemetry_config_invalid_endpoint_bad_scheme():
    """Test TelemetryConfig rejects endpoint with invalid scheme"""
    with pytest.raises(ValueError, match="Invalid endpoint.*Must be http"):
        TelemetryConfig(enabled=True, endpoint="ftp://localhost:4317")


def test_telemetry_config_invalid_endpoint_malformed():
    """Test TelemetryConfig rejects malformed endpoint"""
    with pytest.raises(ValueError, match="Invalid endpoint.*Must be http"):
        TelemetryConfig(enabled=True, endpoint="https://")


def test_telemetry_config_invalid_endpoint_no_host():
    """Test TelemetryConfig rejects endpoint without hostname"""
    with pytest.raises(ValueError, match="Invalid endpoint.*Must be http"):
        TelemetryConfig(enabled=True, endpoint="http://:4317")


def test_telemetry_config_invalid_timeout_zero():
    """Test TelemetryConfig rejects zero timeout"""
    with pytest.raises(ValueError, match="greater than 0"):
        TelemetryConfig(enabled=True, timeout=0)


def test_telemetry_config_invalid_timeout_negative():
    """Test TelemetryConfig rejects negative timeout"""
    with pytest.raises(ValueError, match="greater than 0"):
        TelemetryConfig(enabled=True, timeout=-1)


def test_telemetry_enabled_without_exporters(mock_opentelemetry_modules, mock_app):
    """Test telemetry with enabled=True but no exporters (edge case)"""
    config = TelemetryConfig(enabled=True, endpoint=None, console_export=False)

    # Should warn about no exporters configured
    with pytest.warns(UserWarning, match="no exporters are configured"):
        result = mock_opentelemetry_modules["setup_telemetry"](mock_app, config)

    # Verify tracer was returned (get_tracer was called)
    assert result is not None

    # Verify Resource and TracerProvider were still created
    mock_opentelemetry_modules["Resource"].create.assert_called_once()
    mock_opentelemetry_modules["TracerProvider"].assert_called_once_with(
        resource=mock_opentelemetry_modules["resource"]
    )

    # Verify NO exporters were created
    mock_opentelemetry_modules["OTLPSpanExporter"].assert_not_called()
    mock_opentelemetry_modules["ConsoleSpanExporter"].assert_not_called()

    # Verify NO span processors were added
    mock_opentelemetry_modules["BatchSpanProcessor"].assert_not_called()
    mock_opentelemetry_modules["tracer_provider"].add_span_processor.assert_not_called()

    # Verify set_tracer_provider was called with the provider
    mock_opentelemetry_modules["trace_module"].set_tracer_provider.assert_called_once_with(
        mock_opentelemetry_modules["tracer_provider"]
    )

    # Verify FlaskInstrumentor was still called
    mock_opentelemetry_modules["flask_instrumentor"].instrument_app.assert_called_once_with(
        mock_app
    )


def test_telemetry_deployment_environment(mock_opentelemetry_modules, mock_app):
    """Test telemetry setup with deployment_environment"""
    config = TelemetryConfig(
        enabled=True, endpoint="https://localhost:4317", deployment_environment="production"
    )

    result = mock_opentelemetry_modules["setup_telemetry"](mock_app, config)

    # Verify tracer was returned (get_tracer was called)
    assert result is not None

    # Verify Resource was created with deployment.environment key-value pair
    resource_attrs = mock_opentelemetry_modules["Resource"].create.call_args[0][0]
    assert mock_opentelemetry_modules["DEPLOYMENT_ENVIRONMENT"] in resource_attrs
    assert resource_attrs[mock_opentelemetry_modules["DEPLOYMENT_ENVIRONMENT"]] == "production"

    # Verify set_tracer_provider was called with the provider
    mock_opentelemetry_modules["trace_module"].set_tracer_provider.assert_called_once_with(
        mock_opentelemetry_modules["tracer_provider"]
    )


def test_telemetry_service_instance_id(mock_opentelemetry_modules, mock_app):
    """Test telemetry setup with custom service_instance_id"""
    config = TelemetryConfig(
        enabled=True,
        endpoint="https://localhost:4317",
        service_instance_id="custom-instance-123",
    )

    result = mock_opentelemetry_modules["setup_telemetry"](mock_app, config)

    # Verify tracer was returned (get_tracer was called)
    assert result is not None

    # Verify Resource was created with service.instance.id key-value pair
    resource_attrs = mock_opentelemetry_modules["Resource"].create.call_args[0][0]
    assert mock_opentelemetry_modules["SERVICE_INSTANCE_ID"] in resource_attrs
    assert (
        resource_attrs[mock_opentelemetry_modules["SERVICE_INSTANCE_ID"]] == "custom-instance-123"
    )

    # Verify set_tracer_provider was called with the provider
    mock_opentelemetry_modules["trace_module"].set_tracer_provider.assert_called_once_with(
        mock_opentelemetry_modules["tracer_provider"]
    )


@pytest.mark.no_mock_otel
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
    # Patch importlib.metadata.version directly to raise an exception
    import importlib.metadata

    def mock_version(package_name):
        raise Exception("Version not found")

    monkeypatch.setattr(importlib.metadata, "version", mock_version)

    config = TelemetryConfig(enabled=True, endpoint="https://localhost:4317")
    result = mock_opentelemetry_modules["setup_telemetry"](mock_app, config)

    assert result is not None

    # Verify Resource was created without version attribute
    mock_opentelemetry_modules["Resource"].create.assert_called_once()
    resource_attrs = mock_opentelemetry_modules["Resource"].create.call_args[0][0]
    # Version should not be in resource attributes when import fails
    assert mock_opentelemetry_modules["SERVICE_VERSION"] not in resource_attrs
