"""OpenTelemetry instrumentation setup for the Platzky engine."""

import atexit
import socket
import uuid
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from opentelemetry.trace import Tracer

    from platzky.engine import Engine

# Error messages
_MISSING_EXPORTERS_MSG = (
    "Telemetry is enabled but no exporters are configured. "
    "Set endpoint or console_export=True to export traces."
)
_INVALID_ENDPOINT_FORMAT_MSG = (
    "Invalid endpoint: '{}'. Must be host:port or [http|https]://host[:port]"
)
_INVALID_ENDPOINT_SCHEME_MSG = "Invalid endpoint scheme: '{}'. Must be http or https"
_MISSING_HOSTNAME_MSG = "Invalid endpoint: '{}'. Missing hostname"
_INVALID_ENDPOINT_PORT_MSG = "Invalid endpoint: '{}'. Port must be an integer between 1 and 65535"


def _check_endpoint(endpoint: str) -> None:
    """Raise ValueError unless endpoint is host:port or http(s)://host[:port].

    Args:
        endpoint: Endpoint string to check; IPv6 hosts must be bracketed, e.g. [::1]:4317
    """
    has_scheme = "://" in endpoint
    try:
        parsed = urlparse(endpoint if has_scheme else f"//{endpoint}")
    except ValueError as e:  # unbalanced IPv6 brackets
        raise ValueError(_INVALID_ENDPOINT_FORMAT_MSG.format(endpoint)) from e
    try:
        port = parsed.port
    except ValueError as e:  # non-integer or out of 0-65535
        raise ValueError(_INVALID_ENDPOINT_PORT_MSG.format(endpoint)) from e

    if has_scheme and parsed.scheme not in ("http", "https"):
        raise ValueError(_INVALID_ENDPOINT_SCHEME_MSG.format(parsed.scheme))
    if not has_scheme and (port is None or endpoint.startswith("/")):
        raise ValueError(_INVALID_ENDPOINT_FORMAT_MSG.format(endpoint))
    if not parsed.hostname:
        raise ValueError(_MISSING_HOSTNAME_MSG.format(endpoint))
    if port == 0:
        raise ValueError(_INVALID_ENDPOINT_PORT_MSG.format(endpoint))


class TelemetryConfig(BaseModel):
    """OpenTelemetry configuration for application tracing.

    Attributes:
        enabled: Enable or disable telemetry tracing
        endpoint: OTLP gRPC endpoint (e.g., localhost:4317 or http://localhost:4317)
        console_export: Export traces to console for debugging
        timeout: Timeout in seconds for exporter (default: 10)
        deployment_environment: Deployment environment (e.g., production, staging, dev)
        service_instance_id: Service instance ID (auto-generated if not provided)
        flush_on_request: Flush spans after each request (default: True, may impact latency)
        flush_timeout_ms: Timeout in milliseconds for per-request flush (default: 5000)
        instrument_logging: Enable automatic logging instrumentation (default: True)
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    endpoint: Optional[str] = None
    console_export: bool = False
    timeout: int = Field(default=10, gt=0)
    deployment_environment: Optional[str] = None
    service_instance_id: Optional[str] = None
    flush_on_request: bool = True
    flush_timeout_ms: int = Field(default=5000, gt=0)
    instrument_logging: bool = True

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: Optional[str]) -> Optional[str]:
        """Validate endpoint URL format.

        Accepts OTLP/gRPC spec-compliant formats:
        - host:port (e.g., localhost:4317, [::1]:4317)
        - http://host[:port]
        - https://host[:port]

        Note: grpc:// scheme is NOT supported per OTLP spec and will be rejected.
        """
        if v is not None:
            _check_endpoint(v)
        return v


def setup_telemetry(app: "Engine", telemetry_config: TelemetryConfig) -> Optional["Tracer"]:
    """Setup OpenTelemetry tracing for Flask application.

    Configures and initializes OpenTelemetry tracing with OTLP and/or console exporters.
    Automatically instruments Flask to capture HTTP requests and trace information.
    Optionally instruments logging to add trace context to log records.

    Args:
        app: Engine instance (Flask-based application)
        telemetry_config: Telemetry configuration specifying endpoint and export options

    Returns:
        OpenTelemetry tracer instance if enabled, None otherwise

    Raises:
        ImportError: If OpenTelemetry packages are not installed when telemetry is enabled
        ValueError: If telemetry is enabled but no exporters are configured
    """
    if not telemetry_config.enabled:
        return None

    # Reject telemetry enabled without exporters (creates overhead without benefit)
    if not telemetry_config.endpoint and not telemetry_config.console_export:
        raise ValueError(_MISSING_EXPORTERS_MSG)

    # If already instrumented, return tracer without rebuilding provider/exporters
    if app.telemetry_instrumented:
        from opentelemetry import trace

        return trace.get_tracer(__name__)

    # Import OpenTelemetry modules (will raise ImportError if not installed)
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )
    from opentelemetry.semconv.attributes.service_attributes import (
        SERVICE_NAME,
        SERVICE_VERSION,
    )

    SERVICE_INSTANCE_ID = "service.instance.id"
    DEPLOYMENT_ENVIRONMENT_NAME = "deployment.environment.name"

    service_name = app.config.get("APP_NAME", "platzky")
    resource_attrs: dict[str, str] = {
        SERVICE_NAME: service_name,
    }

    # Auto-detect service version from package metadata
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as get_version

    try:
        resource_attrs[SERVICE_VERSION] = get_version("platzky")
    except PackageNotFoundError:
        pass  # Version not available

    if telemetry_config.deployment_environment:
        resource_attrs[DEPLOYMENT_ENVIRONMENT_NAME] = telemetry_config.deployment_environment

    # Add instance ID (user-provided or auto-generated)
    if telemetry_config.service_instance_id:
        resource_attrs[SERVICE_INSTANCE_ID] = telemetry_config.service_instance_id
    else:
        # Generate unique instance ID: hostname + short UUID
        hostname = socket.gethostname()
        instance_uuid = str(uuid.uuid4())[:8]
        resource_attrs[SERVICE_INSTANCE_ID] = f"{hostname}-{instance_uuid}"

    resource = Resource.create(resource_attrs)
    provider = TracerProvider(resource=resource)

    # Configure exporter based on endpoint
    if telemetry_config.endpoint:
        exporter = OTLPSpanExporter(
            endpoint=telemetry_config.endpoint, timeout=telemetry_config.timeout
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))

    # Optional console export
    if telemetry_config.console_export:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    FlaskInstrumentor().instrument_app(app)

    # Instrument logging to add trace context to log records
    # Note: set_logging_format=False to avoid modifying existing log formats
    # Users can access trace context in their custom formatters via log record attributes
    if telemetry_config.instrument_logging:
        LoggingInstrumentor().instrument(set_logging_format=False)

    app.telemetry_instrumented = True

    # Optionally flush spans after each request (may impact latency)
    if telemetry_config.flush_on_request:

        @app.teardown_appcontext
        def flush_telemetry(_exc: Optional[BaseException] = None) -> None:
            """Flush pending spans after request completion."""
            provider.force_flush(timeout_millis=telemetry_config.flush_timeout_ms)

    # Shutdown provider once at process exit
    atexit.register(provider.shutdown)

    return trace.get_tracer(__name__)
