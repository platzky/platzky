# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportPossiblyUnboundVariable=false
import socket
import uuid
import warnings

from platzky.config import TelemetryConfig

try:
    from opentelemetry import trace
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
    from opentelemetry.semconv.resource import ResourceAttributes

    _otel_available = True
except ImportError:
    _otel_available = False


def setup_telemetry(app, telemetry_config: TelemetryConfig):
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

    # Build resource attributes
    service_name = app.config.get("APP_NAME", "platzky")
    resource_attrs = {
        ResourceAttributes.SERVICE_NAME: service_name,
    }

    # Auto-detect service version from package metadata
    try:
        from importlib.metadata import version as get_version

        resource_attrs[ResourceAttributes.SERVICE_VERSION] = get_version("platzky")
    except Exception:
        pass  # Version not available

    if telemetry_config.deployment_environment:
        resource_attrs[ResourceAttributes.DEPLOYMENT_ENVIRONMENT] = (
            telemetry_config.deployment_environment
        )

    # Add instance ID (user-provided or auto-generated)
    if telemetry_config.service_instance_id:
        resource_attrs[ResourceAttributes.SERVICE_INSTANCE_ID] = (
            telemetry_config.service_instance_id
        )
    else:
        # Generate unique instance ID: hostname + short UUID
        hostname = socket.gethostname()
        instance_uuid = str(uuid.uuid4())[:8]
        resource_attrs[ResourceAttributes.SERVICE_INSTANCE_ID] = f"{hostname}-{instance_uuid}"

    resource = Resource.create(resource_attrs)
    provider = TracerProvider(resource=resource)

    # Warn if telemetry is enabled but no exporters configured
    if not telemetry_config.endpoint and not telemetry_config.console_export:
        warnings.warn(
            "Telemetry is enabled but no exporters are configured. "
            "Set endpoint or console_export=True to export traces.",
            UserWarning,
            stacklevel=2,
        )

    # Configure exporter based on endpoint
    if telemetry_config.endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(
            endpoint=telemetry_config.endpoint, timeout=telemetry_config.timeout
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))

    # Optional console export
    if telemetry_config.console_export:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    FlaskInstrumentor().instrument_app(app)

    return trace.get_tracer(__name__)
