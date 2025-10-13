import atexit
import socket
import uuid
from typing import TYPE_CHECKING, Optional

from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes

from platzky.config import TelemetryConfig

if TYPE_CHECKING:
    from opentelemetry.trace import Tracer

    from platzky.engine import Engine

# Error messages
_MISSING_EXPORTERS_MSG = (
    "Telemetry is enabled but no exporters are configured. "
    "Set endpoint or console_export=True to export traces."
)


def setup_telemetry(app: "Engine", telemetry_config: TelemetryConfig) -> Optional["Tracer"]:
    """Setup OpenTelemetry tracing for Flask application.

    Configures and initializes OpenTelemetry tracing with OTLP and/or console exporters.
    Automatically instruments Flask to capture HTTP requests and trace information.

    Args:
        app: Flask application instance
        telemetry_config: Telemetry configuration specifying endpoint and export options

    Returns:
        OpenTelemetry tracer instance if enabled, None otherwise
    """

    if not telemetry_config.enabled:
        return None

    # Build resource attributes
    service_name = app.config.get("APP_NAME", "platzky")
    resource_attrs: dict[str, str] = {
        ResourceAttributes.SERVICE_NAME: service_name,
    }

    # Auto-detect service version from package metadata
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as get_version

    try:
        resource_attrs[ResourceAttributes.SERVICE_VERSION] = get_version("platzky")
    except PackageNotFoundError:
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

    # Reject telemetry enabled without exporters (creates overhead without benefit)
    if not telemetry_config.endpoint and not telemetry_config.console_export:
        raise ValueError(_MISSING_EXPORTERS_MSG)

    resource = Resource.create(resource_attrs)
    provider = TracerProvider(resource=resource)

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

    # Flush spans after each request to avoid losing data
    @app.teardown_appcontext
    def flush_telemetry(_exc: Optional[BaseException] = None) -> None:
        """Flush pending spans after request completion."""
        provider.force_flush()

    # Shutdown provider once at process exit
    atexit.register(provider.shutdown)

    return trace.get_tracer(__name__)
