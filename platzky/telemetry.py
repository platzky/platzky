# pyright: reportMissingImports=false, reportPossiblyUnboundVariable=false, reportAttributeAccessIssue=false
import os

from platzky.config import TelemetryConfig

try:
    from opentelemetry import trace
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _otel_available = True
except ImportError:
    _otel_available = False


def setup_telemetry(app, telemetry_config: TelemetryConfig):
    """Setup OpenTelemetry tracing for Flask app"""

    if not telemetry_config.enabled:
        return None

    if not _otel_available:
        raise ImportError(
            "OpenTelemetry is not installed. Install with: "
            "poetry add opentelemetry-api opentelemetry-sdk "
            "opentelemetry-instrumentation-flask opentelemetry-exporter-otlp-proto-grpc"
        )

    service_name = app.config.get("APP_NAME", "platzky")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    # Configure exporter based on config
    if telemetry_config.exporter == "gcp-trace":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        # Use Cloud Trace OTLP endpoint
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set")

        exporter = OTLPSpanExporter(
            endpoint=f"https://cloudtrace.googleapis.com/v2/projects/{project_id}/traces:batchWrite"
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))

    elif telemetry_config.exporter == "otlp":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        endpoint = telemetry_config.otlp_endpoint or "http://localhost:4317"
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    elif telemetry_config.exporter == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    # Optional console export alongside other exporters
    if telemetry_config.console_export and telemetry_config.exporter != "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    FlaskInstrumentor().instrument_app(app)

    return trace.get_tracer(__name__)
