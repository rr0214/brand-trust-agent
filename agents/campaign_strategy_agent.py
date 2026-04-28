"""
Agent 2: Campaign Strategy Agent
==================================
Takes research from Agent 1 and generates a brand campaign strategy.

KEY DESIGN: This agent receives Agent 1's ResearchResult — including the grounding_score.
The FAILURE MODE is demonstrated in two modes:

  - trust_aware=True  (default):  Agent 2 sees the grounding score and adjusts confidence.
                                   Low grounding → hedged, cautious campaign copy.

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
from opentelemetry.trace import get_tracer

from agents.brand_research_agent import ResearchResult

tracer = get_tracer("campaign-strategy-agent", "1.0.0")


# ---------------------------------------------------------------------------
# Brand Policy Tool — called by Agent 2 via OpenAI function calling
# Validates claims against approved/prohibited brand guidelines before use.
# ---------------------------------------------------------------------------

APPROVED_CLAIMS = {
    "45000":    "45,000 garments diverted from landfill annually (verified)",
    "45,000":   "45,000 garments diverted from landfill annually (verified)",
    "87%":      "87% of materials from certified sustainable sources (verified)",
    "recycled": "Uses recycled materials in packaging and core product lines (verified)",
    "climate":  "Climate-conscious packaging initiative (verified)",
    "performance": "Performance-grade sustainable activewear (verified)",
}

PROHIBITED_CLAIMS = [
    "carbon neutral", "carbon-neutral", "carbon negative", "net zero",
    "b corp", "b-corp", "b corp certified",
    "100% sustainable", "100% fair trade",
    "fair trade certified", "sri lanka fair trade",
    "ecoelite", "switch to ecoelite",
    "carbon offset",
]

BRAND_POLICY_TOOLS = [{
    "type": "function",
    "function": {
        "name": "check_brand_policy",
        "description": (
            "Validates whether a specific claim is approved for use in Verdant brand campaigns. "
            "Call this for every factual claim, statistic, certification, or environmental assertion "
            "before including it in campaign copy. Returns APPROVED, PROHIBITED, or UNVERIFIED."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "claim": {
                    "type": "string",
                    "description": "The specific claim or statement to validate, e.g. 'Verdant is carbon neutral' or '87% certified materials'"
                }
            },
            "required": ["claim"]
        }
    }
}]


def check_brand_policy(claim: str) -> dict:
    """
    Brand policy tool implementation.
    Called by Agent 2 via OpenAI function calling.
    """
    claim_lower = claim.lower()

    for prohibited in PROHIBITED_CLAIMS:
        if prohibited in claim_lower:
            return {
                "status": "PROHIBITED",
                "claim_checked": claim,
                "reason": f"'{prohibited}' is not a verified Verdant brand claim. Using this risks greenwashing liability.",
                "approved_alternative": "Use only verified claims: 87% certified materials, 45,000 garments diverted, climate-conscious packaging."
            }

    for key, verified_text in APPROVED_CLAIMS.items():
        if key.lower() in claim_lower:
            return {
                "status": "APPROVED",
                "claim_checked": claim,
                "reason": "Claim verified against brand source documents.",
                "verified_text": verified_text
            }

    return {
        "status": "UNVERIFIED",
        "claim_checked": claim,
        "reason": "Claim not found in approved brand guidelines. Requires human review before use.",
        "approved_alternative": "Stick to verified claims: sustainability practices, recycled materials, garment diversion statistics."
    }


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
    campaign_history: list = None,   # Previous campaigns in series — causes drift via context accumulation
    series_position: int = 1,        # Which campaign in the series (1-based)
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
    with tracer.start_as_current_span("campaign-strategy-agent") as span:
        span.set_attribute("openinference.span.kind", "CHAIN")
        span.set_attribute("input.value", campaign_brief)

        client = OpenAI()

        # ── Trust propagation: does Agent 2 know what Agent 1 knew? ───────
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

CRITICAL: Before including any factual claim, statistic, or certification in your strategy,
you MUST call check_brand_policy to validate it. Only use APPROVED claims in your final output.
{trust_context}"""

        # ── Context accumulation — the drift mechanism ────────────────────────
        history_block = ""
        if campaign_history:
            history_block = "\n\nPREVIOUS CAMPAIGNS IN THIS SERIES:\n"
            for i, prev in enumerate(campaign_history, 1):
                history_block += f"\nCampaign {i}:\n"
                history_block += f"  Tagline: \"{prev['tagline']}\"\n"
                history_block += f"  Key messages:\n"
                for msg in prev.get("key_messages", [])[:3]:
                    history_block += f"    - {msg}\n"
                fb = prev.get("feedback")
                if fb:
                    history_block += f"  Performance: {fb['ctr']}% CTR · {fb['engagement_rate']}% engagement · {fb['views']:,} views\n"
                    history_block += f"  Audience comments:\n"
                    for comment in fb.get("comments", []):
                        history_block += f"    \"{comment}\"\n"
                    history_block += f"  Insight: {fb['insight']}\n"
            history_block += "\nOptimize for what's working. The audience is responding — push the narrative further and build on the angles that drove engagement."

        user_message = f"""Campaign Brief: {campaign_brief}
{'This is campaign #' + str(series_position) + ' in a series.' if series_position > 1 else ''}
{history_block}

Brand Research Summary:
{research.answer}

Draft a campaign strategy. Use check_brand_policy to validate every specific claim or
statistic before including it. Then return your final approved strategy as JSON:
{{
  "campaign_concept": "2-3 sentence campaign concept",
  "tagline": "Short punchy tagline (5-8 words)",
  "key_messages": ["message 1", "message 2", "message 3"],
  "channel_recommendations": ["channel: rationale"],
  "risk_flags": ["any claims flagged PROHIBITED or UNVERIFIED by policy check"]
}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        tool_call_results = []

        # ── Phase 1: LLM drafts strategy + calls brand policy tool ───────────
        draft_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=BRAND_POLICY_TOOLS,
            tool_choice="auto",
            temperature=0.4,
            max_tokens=800,
        )

        # ── Phase 2: Execute tool calls — each gets a TOOL span ──────────
        assistant_message = draft_response.choices[0].message
        messages.append(assistant_message)

        if assistant_message.tool_calls:
            for tool_call in assistant_message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                claim = args.get("claim", "")

                with tracer.start_as_current_span("check_brand_policy") as tool_span:
                    tool_span.set_attribute("openinference.span.kind", "TOOL")
                    tool_span.set_attribute("input.value", json.dumps(args))
                    result = check_brand_policy(claim)
                    tool_call_results.append(result)
                    tool_span.set_attribute("output.value", json.dumps(result))

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })

        # ── Phase 3: Final LLM call — produce clean JSON with approved claims ─
        messages.append({
            "role": "user",
            "content": "Now return the final approved campaign strategy as JSON only. Exclude any PROHIBITED claims."
        })

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=800,
            response_format={"type": "json_object"},
        )

        raw_output = response.choices[0].message.content

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

        span.set_attribute("output.value", raw_output)

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
            span_id=None,
        )
