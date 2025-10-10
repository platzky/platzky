import socket
import uuid
from typing import TYPE_CHECKING, Any, Optional

from platzky.config import TelemetryConfig

# OpenTelemetry is an optional dependency - we check availability at runtime
_otel_available = False

try:
    from opentelemetry import trace
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
    from opentelemetry.semconv.resource import ResourceAttributes

    _otel_available = True
except ImportError:
    # OpenTelemetry not installed - we'll handle this in setup_telemetry()
    if not TYPE_CHECKING:
        # Provide stub objects for runtime only (type checkers won't see this branch)
        trace = None  # type: ignore
        FlaskInstrumentor = None  # type: ignore
        Resource = None  # type: ignore
        TracerProvider = None  # type: ignore
        BatchSpanProcessor = None  # type: ignore
        SimpleSpanProcessor = None  # type: ignore
        ResourceAttributes = None  # type: ignore


def setup_telemetry(app: Any, telemetry_config: TelemetryConfig) -> Optional[Any]:
    """Setup OpenTelemetry tracing for Flask application.

    Configures and initializes OpenTelemetry tracing with OTLP and/or console exporters.
    Automatically instruments Flask to capture HTTP requests and trace information.

    Args:
        app: Flask application instance
        telemetry_config: Telemetry configuration specifying endpoint and export options

    Returns:
        OpenTelemetry tracer instance if enabled, None otherwise

    Raises:
        ImportError: If OpenTelemetry packages are not installed when telemetry is enabled
    """

    if not telemetry_config.enabled:
        return None

    if not _otel_available:
        raise ImportError(
            "OpenTelemetry is not installed. Install with: "
            "poetry add opentelemetry-api opentelemetry-sdk "
            "opentelemetry-instrumentation-flask opentelemetry-exporter-otlp-proto-grpc"
        )

    # At this point, _otel_available is True, so all OpenTelemetry imports are available
    # Type checkers can't infer this, so we use type: ignore comments below

    # Build resource attributes
    service_name = app.config.get("APP_NAME", "platzky")
    resource_attrs = {
        ResourceAttributes.SERVICE_NAME: service_name,  # type: ignore[attr-defined]
    }

    # Auto-detect service version from package metadata
    try:
        from importlib.metadata import version as get_version

        resource_attrs[ResourceAttributes.SERVICE_VERSION] = get_version("platzky")  # type: ignore[attr-defined]
    except Exception:
        pass  # Version not available

    if telemetry_config.deployment_environment:
        resource_attrs[ResourceAttributes.DEPLOYMENT_ENVIRONMENT] = (  # type: ignore[attr-defined]
            telemetry_config.deployment_environment
        )

    # Add instance ID (user-provided or auto-generated)
    if telemetry_config.service_instance_id:
        resource_attrs[ResourceAttributes.SERVICE_INSTANCE_ID] = (  # type: ignore[attr-defined]
            telemetry_config.service_instance_id
        )
    else:
        # Generate unique instance ID: hostname + short UUID
        hostname = socket.gethostname()
        instance_uuid = str(uuid.uuid4())[:8]
        resource_attrs[ResourceAttributes.SERVICE_INSTANCE_ID] = f"{hostname}-{instance_uuid}"  # type: ignore[attr-defined]

    # Reject telemetry enabled without exporters (creates overhead without benefit)
    if not telemetry_config.endpoint and not telemetry_config.console_export:
        raise ValueError(
            "Telemetry is enabled but no exporters are configured. "
            "Set endpoint or console_export=True to export traces."
        )

    resource = Resource.create(resource_attrs)  # type: ignore[attr-defined]
    provider = TracerProvider(resource=resource)  # type: ignore[misc]

    # Configure exporter based on endpoint
    if telemetry_config.endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(
            endpoint=telemetry_config.endpoint, timeout=telemetry_config.timeout
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))  # type: ignore[misc]

    # Optional console export
    if telemetry_config.console_export:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))  # type: ignore[misc]

    trace.set_tracer_provider(provider)  # type: ignore[attr-defined]
    FlaskInstrumentor().instrument_app(app)  # type: ignore[misc]

    return trace.get_tracer(__name__)  # type: ignore[attr-defined]
