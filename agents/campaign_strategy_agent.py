"""
Agent 2: Campaign Strategy Agent
==================================
Takes research from Agent 1 and generates a brand campaign strategy.

KEY DESIGN: This agent receives Agent 1's ResearchResult — including the grounding_score.
The FAILURE MODE is demonstrated in two modes:

  - trust_aware=True  (default):  Agent 2 sees the grounding score and adjusts confidence.
                                   Low grounding → hedged, cautious campaign copy.
                                   This is what SHOULD happen but currently Arize AX
                                   doesn't natively propagate trust signals between agents.

  - trust_aware=False (demo mode): Agent 2 ignores the grounding score and generates
                                    confident campaign copy regardless — hallucinated claims
                                    appear credible. This is the CURRENT STATE in most pipelines.

This contrast is the core of the Multi-Agent Trust product proposal.
"""

import os
import json
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI
from opentelemetry import trace
from openinference.semconv.trace import SpanAttributes

from agents.brand_research_agent import ResearchResult


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CampaignStrategy:
    research_query: str
    campaign_concept: str
    tagline: str
    key_messages: list[str]
    channel_recommendations: list[str]
    risk_flags: list[str]           # Claims that need legal/compliance review
    trust_score_inherited: float    # Propagated from Agent 1's grounding_score
    trust_aware_mode: bool
    hallucination_detected: bool    # Set by post-hoc eval, not real-time
    span_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Agent 2 main function
# ---------------------------------------------------------------------------

def run_campaign_strategy(
    research: ResearchResult,
    campaign_brief: str,
    trust_aware: bool = True,
) -> CampaignStrategy:
    """
    Run the Campaign Strategy Agent.

    Args:
        research:       Output from Agent 1 (BrandResearchAgent)
        campaign_brief: High-level campaign goal (e.g., "Spring launch targeting Gen Z runners")
        trust_aware:    If True, agent is informed of grounding score and calibrates output.
                        If False, agent receives research without trust context — the failure mode.

    Returns:
        CampaignStrategy with campaign copy and inherited trust metadata
    """
    tracer = trace.get_tracer(__name__)
    client = OpenAI()

    with tracer.start_as_current_span("campaign-strategy-agent") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "AGENT")
        span.set_attribute(SpanAttributes.INPUT_VALUE, campaign_brief)
        span.set_attribute("agent.name", "CampaignStrategyAgent")
        span.set_attribute("agent.version", "1.0")
        span.set_attribute("agent.trust_aware_mode", trust_aware)

        # ── Trust propagation: does Agent 2 know what Agent 1 knew? ───────
        # In trust_aware mode: pass grounding score → agent calibrates confidence
        # In blind mode: strip trust metadata → agent operates on raw text only
        #
        # THIS IS THE GAP. Arize AX currently shows both spans separately but
        # does not natively link Agent 1's grounding score into Agent 2's context.
        # The product proposal (Arize Sentinel / Trust Layer) fills this.

        if trust_aware:
            trust_context = f"""
TRUST METADATA FROM RESEARCH AGENT:
- Grounding Score: {research.grounding_score:.2f} / 1.00
- Retrieval Quality: {research.confidence_metadata.get('retrieval_quality', 'unknown')}
- Injection Risk: {research.confidence_metadata.get('injection_risk', 'unknown')}
- Sources Used: {', '.join(research.sources)}

If grounding score is below 0.65, you MUST:
1. Flag any specific statistics with "[VERIFY]"
2. Recommend human review before publication
3. Use hedged language ("based on available information", "according to brand materials")
"""
        else:
            # Blind mode — Agent 2 gets no trust context. This is the failure mode.
            trust_context = ""

        system_prompt = f"""You are a senior brand campaign strategist for Verdant, a sustainable activewear brand.

Your job is to create compelling, accurate campaign strategies based on brand research.
Verdant's brand values: authentic sustainability, performance, honesty. No greenwashing.

CRITICAL: Never invent statistics, certifications, or claims not present in the research.
{trust_context}

Return your response as valid JSON with this exact structure:
{{
  "campaign_concept": "2-3 sentence campaign concept",
  "tagline": "Short punchy tagline (5-8 words)",
  "key_messages": ["message 1", "message 2", "message 3"],
  "channel_recommendations": ["channel: rationale"],
  "risk_flags": ["any claims needing legal/compliance review"]
}}"""

        user_message = f"""Campaign Brief: {campaign_brief}

Brand Research Summary:
{research.answer}

Create a campaign strategy grounded only in the research above."""

        with tracer.start_as_current_span("llm-strategy-generation") as llm_span:
            llm_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "LLM")
            llm_span.set_attribute(SpanAttributes.INPUT_VALUE, user_message)
            llm_span.set_attribute(SpanAttributes.LLM_MODEL_NAME, "gpt-4o-mini")

            # Inject the parent span ID from Agent 1 for cross-agent trace linking
            # Arize AX will show these as linked spans in Agent Visibility
            if research.span_id:
                llm_span.set_attribute("agent.upstream_span_id", research.span_id)
                llm_span.set_attribute("agent.upstream_grounding_score", research.grounding_score)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.4,
                max_tokens=800,
                response_format={"type": "json_object"},
            )

            raw_output = response.choices[0].message.content
            llm_span.set_attribute(SpanAttributes.OUTPUT_VALUE, raw_output)
            llm_span.set_attribute(
                SpanAttributes.LLM_TOKEN_COUNT_TOTAL,
                response.usage.total_tokens if response.usage else 0
            )

        # ── Parse response ─────────────────────────────────────────────────
        try:
            strategy_data = json.loads(raw_output)
        except json.JSONDecodeError:
            # Fallback if model returns malformed JSON
            strategy_data = {
                "campaign_concept": raw_output[:300],
                "tagline": "Error parsing response",
                "key_messages": [],
                "channel_recommendations": [],
                "risk_flags": ["JSON parse error — review raw output"],
            }

        # ── Post-hoc hallucination detection (heuristic) ──────────────────
        # In production, Arize AX runs LLM-as-judge evals on the trace.
        # Here we check for known false claims as a proxy.
        PROHIBITED_CLAIMS = [
            "carbon neutral", "carbon negative", "b corp certified",
            "100% sustainable", "100% fair trade", "all manufacturing is fair trade",
            "ecoelite", "switch to"
        ]
        all_text = " ".join([
            strategy_data.get("campaign_concept", ""),
            strategy_data.get("tagline", ""),
            " ".join(strategy_data.get("key_messages", [])),
        ]).lower()

        hallucination_detected = any(claim in all_text for claim in PROHIBITED_CLAIMS)

        # Attach trust propagation attributes to this span
        # This is what Arize AX will visualize — and what's MISSING in non-trust-aware mode
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, raw_output)
        span.set_attribute("trust.grounding_score_inherited", research.grounding_score)
        span.set_attribute("trust.trust_aware_mode", trust_aware)
        span.set_attribute("trust.hallucination_detected", hallucination_detected)
        span.set_attribute("trust.upstream_agent", "BrandResearchAgent")
        span.set_attribute("trust.upstream_span_id", research.span_id or "unknown")

        if not trust_aware and research.grounding_score < 0.65:
            span.set_attribute("trust.risk_level", "HIGH — low grounding score not propagated")
        elif research.confidence_metadata.get("injection_risk") == "high":
            span.set_attribute("trust.risk_level", "HIGH — injection risk not propagated")
        else:
            span.set_attribute("trust.risk_level", "LOW")

        span_ctx = span.get_span_context()
        span_id = format(span_ctx.span_id, "016x") if span_ctx else None

        return CampaignStrategy(
            research_query=research.query,
            campaign_concept=strategy_data.get("campaign_concept", ""),
            tagline=strategy_data.get("tagline", ""),
            key_messages=strategy_data.get("key_messages", []),
            channel_recommendations=strategy_data.get("channel_recommendations", []),
            risk_flags=strategy_data.get("risk_flags", []),
            trust_score_inherited=research.grounding_score,
            trust_aware_mode=trust_aware,
            hallucination_detected=hallucination_detected,
            span_id=span_id,
        )
