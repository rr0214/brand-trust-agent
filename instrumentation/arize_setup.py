"""
Arize AX instrumentation setup.
Registers the OTLP exporter pointed at Arize cloud and auto-instruments OpenAI calls.
"""

import os
from arize.otel import register
from openinference.instrumentation.openai import OpenAIInstrumentor


def _get_secret(key: str) -> str | None:
    """
    Read a secret from environment variables first, then fall back to Streamlit secrets.
    This lets the app work locally (via .env) and on Streamlit Cloud (via st.secrets).
    """
    val = os.environ.get(key)
    if val:
        return val
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val:
            # Inject into os.environ so downstream code (OpenAI SDK etc.) can also see it
            os.environ[key] = val
        return val
    except Exception:
        return None


def setup_arize_tracing() -> None:
    """
    Initialize Arize AX tracing. Call once at application startup (before any OpenAI calls).

    Required (via .env or Streamlit secrets):
        ARIZE_SPACE_ID  — found in Arize AX under Settings > API Keys
        ARIZE_API_KEY   — found in Arize AX under Settings > API Keys

    The model_id ("brand-trust-agent") becomes the Project name in Arize AX.
    """
    space_id = _get_secret("ARIZE_SPACE_ID")
    api_key = _get_secret("ARIZE_API_KEY")

    if not space_id or not api_key:
        raise ValueError(
            "ARIZE_SPACE_ID and ARIZE_API_KEY must be set in environment. "
            "Find them at app.arize.com > Settings > API Keys."
        )

    tracer_provider = register(
        space_id=space_id,
        api_key=api_key,
        project_name="brand-trust-agent",
    )

    # Auto-instrument all OpenAI SDK calls — every chat completion and embedding
    # will automatically create a span with input/output captured.
    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

    return tracer_provider
