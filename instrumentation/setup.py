"""
Arize AX tracing setup.

Registers the OTLP exporter and auto-instruments OpenAI calls.
Call setup_tracing() once at application startup, before creating any LLM clients.

Required env vars:
    ARIZE_SPACE_ID  — from app.arize.com > Settings > API Keys
    ARIZE_API_KEY   — from app.arize.com > Settings > API Keys
"""

import os
import logging

logger = logging.getLogger(__name__)


def setup_tracing():
    """
    Initialize Arize AX tracing. Returns the tracer provider, or None if
    credentials are missing (app continues without tracing).
    """
    space_id = os.environ.get("ARIZE_SPACE_ID")
    api_key = os.environ.get("ARIZE_API_KEY")

    if not space_id or not api_key:
        # Also check Streamlit secrets as fallback
        try:
            import streamlit as st
            space_id = space_id or st.secrets.get("ARIZE_SPACE_ID")
            api_key = api_key or st.secrets.get("ARIZE_API_KEY")
            if space_id:
                os.environ["ARIZE_SPACE_ID"] = space_id
            if api_key:
                os.environ["ARIZE_API_KEY"] = api_key
        except Exception:
            pass

    if not space_id or not api_key:
        logger.warning("ARIZE_SPACE_ID and ARIZE_API_KEY not set — tracing disabled.")
        return None

    from arize.otel import register
    from openinference.instrumentation.openai import OpenAIInstrumentor

    tracer_provider = register(
        space_id=space_id,
        api_key=api_key,
        project_name="brand-trust-agent-auto",
    )

    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

    return tracer_provider
