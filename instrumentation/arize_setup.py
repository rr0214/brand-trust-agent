"""
Arize AX instrumentation setup.
Registers the OTLP exporter pointed at Arize cloud and auto-instruments OpenAI calls.
"""

import os
from arize.otel import register
from openinference.instrumentation.openai import OpenAIInstrumentor


def setup_arize_tracing() -> None:
    """
    Initialize Arize AX tracing. Call once at application startup (before any OpenAI calls).

    Required environment variables:
        ARIZE_SPACE_ID  — found in Arize AX under Settings > API Keys
        ARIZE_API_KEY   — found in Arize AX under Settings > API Keys

    The model_id ("brand-trust-agent") becomes the Project name in Arize AX.
    """
    space_id = os.environ.get("ARIZE_SPACE_ID")
    api_key = os.environ.get("ARIZE_API_KEY")

    if not space_id or not api_key:
        raise ValueError(
            "ARIZE_SPACE_ID and ARIZE_API_KEY must be set in environment. "
            "Find them at app.arize.com > Settings > API Keys."
        )

    tracer_provider = register(
        space_id=space_id,
        api_key=api_key,
        model_id="brand-trust-agent",
        model_version="1.0",
    )

    # Auto-instrument all OpenAI SDK calls — every chat completion and embedding
    # will automatically create a span with input/output captured.
    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

    return tracer_provider
