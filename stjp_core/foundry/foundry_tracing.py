"""
Configure OpenTelemetry tracing -> Azure Application Insights so that runs
appear in the Foundry portal's Tracing tab.

Call enable_foundry_tracing() once at startup, before any agent calls.
"""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# Canonical .env lives at stjp_core/.env (this file is stjp_core/foundry/).
load_dotenv(Path(__file__).parent.parent / ".env")
from stjp_core.foundry.az_credential import AzCliCredential


_INSTRUMENTED = False


def enable_foundry_tracing(service_name: str = "stjp-experiment") -> str | None:
    """Wire OpenTelemetry to the project's Application Insights connection.

    Returns the connection string used (None if disabled / failed).
    """
    global _INSTRUMENTED
    if os.environ.get("STJP_DISABLE_TRACING") == "1":
        return None
    if _INSTRUMENTED:
        return os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    # Required so genai content (prompts/responses) is captured in spans
    os.environ.setdefault("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING", "true")
    os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")
    os.environ.setdefault("AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED", "true")

    from azure.ai.projects import AIProjectClient
    project = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    if not project:
        print("[trace] AZURE_AI_PROJECT_ENDPOINT not set; tracing disabled.")
        return None

    client = AIProjectClient(endpoint=project, credential=AzCliCredential())
    conn_str = client.telemetry.get_application_insights_connection_string()
    if not conn_str:
        print("[trace] No AppInsights connection on project; tracing disabled.")
        return None
    os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] = conn_str

    # Configure Azure Monitor exporter
    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor(
        connection_string=conn_str,
        resource_attributes={"service.name": service_name},
    )

    # Tell azure-core to emit OTel spans for SDK calls
    try:
        from azure.core.settings import settings
        from azure.core.tracing.ext.opentelemetry_span import OpenTelemetrySpan
        settings.tracing_implementation = OpenTelemetrySpan
    except Exception as e:
        print(f"[trace] azure-core OTel adapter not wired: {e}")

    # Instrument the OpenAI SDK so chat/agent calls emit gen_ai.* spans
    try:
        from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
        OpenAIInstrumentor().instrument()
    except Exception as e:
        print(f"[trace] OpenAI instrumentation not wired: {e}")

    _INSTRUMENTED = True
    print(f"[trace] tracing enabled -> {conn_str.split(';')[1]}")
    return conn_str
