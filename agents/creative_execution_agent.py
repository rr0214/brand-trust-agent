"""
Agent 3: Creative Execution Agent
===================================
Takes the approved campaign strategy from Agent 2 and produces a complete
social media creative package:
  - A 5-second Veo 2 campaign video (Google Gen AI)
  - Social media caption + hashtags (GPT-4o-mini)

TRUST GATE: If upstream trust signals indicate hallucination or critically low
grounding, the pipeline halts before any creative assets are generated.
This is the "take action" principle — not just flagging bad output, but
refusing to produce creative assets from unverified brand claims.

Arize AX trace structure:
  creative-execution-agent (AGENT)
    ├── prompt-engineering (LLM)       — builds brand-safe video prompt
    ├── veo-video-generation (TOOL)    — generates 5s social video via Veo 2
    └── caption-generation (LLM)      — writes social caption + hashtags
"""

import os
import time
import json
import base64
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI
from opentelemetry import trace
from openinference.semconv.trace import SpanAttributes

from agents.campaign_strategy_agent import CampaignStrategy

# Trust threshold — below this, pipeline halts, no creative generated
CRITICAL_TRUST_THRESHOLD = 0.30

# Verdant brand visual guidelines
VERDANT_VISUAL_GUIDELINES = """
Verdant brand visual identity:
- Color palette: deep forest greens, warm earth tones, clean whites
- Aesthetic: clean, natural, active, authentic — NOT corporate or stock-photo
- Setting: outdoor environments, urban parks, trails, natural light
- People: diverse, active, real — not models posing
- Mood: energetic but grounded, aspirational but honest
- Style: editorial photography aesthetic, cinematic, natural textures
- No text overlays, no logos, no studio backgrounds
"""


@dataclass
class CreativeResult:
    status: str                          # APPROVED | HALTED | ERROR
    campaign_concept: str
    tagline: str
    video_url: Optional[str]             # Veo 2 generated video URL
    video_bytes: Optional[bytes]         # Raw video bytes if URL not available
    video_prompt: Optional[str]          # Prompt used to generate video
    caption: Optional[str]              # Social media caption
    hashtags: Optional[list]            # Suggested hashtags
    halt_reason: Optional[str]          # Why pipeline halted (if applicable)
    trust_score_inherited: float
    span_id: Optional[str] = None


def run_creative_execution(
    strategy: CampaignStrategy,
    brand_name: str = "Verdant",
) -> CreativeResult:
    """
    Run the Creative Execution Agent.

    Trust gate enforced first — if upstream signals are bad, halt immediately.
    Otherwise: build video prompt → generate Veo 2 video → write social caption.
    """
    tracer = trace.get_tracer(__name__)
    openai_client = OpenAI()

    with tracer.start_as_current_span("creative-execution-agent") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "AGENT")
        span.set_attribute("agent.name", "CreativeExecutionAgent")
        span.set_attribute("agent.version", "1.0")
        span.set_attribute("agent.upstream_agent", "CampaignStrategyAgent")
        span.set_attribute("agent.upstream_span_id", strategy.span_id or "unknown")
        span.set_attribute("trust.grounding_score_inherited", strategy.trust_score_inherited)
        span.set_attribute("trust.hallucination_detected_upstream", strategy.hallucination_detected)

        # ── TRUST GATE ────────────────────────────────────────────────────────
        if strategy.hallucination_detected:
            halt_reason = (
                "Pipeline halted: prohibited brand claims detected in campaign strategy. "
                "No creative assets will be generated from unverified content. "
                "This prevents brand misrepresentation and potential legal liability."
            )
            span.set_attribute("trust.pipeline_halted", True)
            span.set_attribute("trust.halt_reason", "hallucination_detected")
            return _halted_result(strategy, halt_reason, span)

        if strategy.trust_score_inherited < CRITICAL_TRUST_THRESHOLD:
            halt_reason = (
                f"Pipeline halted: grounding score ({strategy.trust_score_inherited:.2f}) "
                f"below critical threshold ({CRITICAL_TRUST_THRESHOLD}). "
                "Campaign strategy lacks sufficient brand evidence. "
                "Expand retrieval corpus before proceeding to creative execution."
            )
            span.set_attribute("trust.pipeline_halted", True)
            span.set_attribute("trust.halt_reason", "critical_low_grounding")
            return _halted_result(strategy, halt_reason, span)

        span.set_attribute("trust.pipeline_halted", False)

        # ── PHASE 1: Build brand-safe video prompt ────────────────────────────
        with tracer.start_as_current_span("prompt-engineering") as prompt_span:
            prompt_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "LLM")
            prompt_span.set_attribute(SpanAttributes.LLM_MODEL_NAME, "gpt-4o-mini")

            prompt_input = f"""You are a creative director for {brand_name}, a sustainable activewear brand.

Brand visual guidelines:
{VERDANT_VISUAL_GUIDELINES}

Campaign concept: {strategy.campaign_concept}
Tagline: {strategy.tagline}
Key messages: {', '.join(strategy.key_messages[:2])}

Write a cinematic video prompt for a 5-second social media campaign video (max 150 words):
- Describe a single continuous scene or motion
- Follow Verdant brand visual guidelines strictly
- No text, logos, or words in the video
- Cinematic, natural, authentic
- Suitable for Instagram Reels or TikTok

Return only the video prompt, nothing else."""

            prompt_span.set_attribute(SpanAttributes.INPUT_VALUE, prompt_input)

            prompt_response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt_input}],
                temperature=0.6,
                max_tokens=200,
            )

            video_prompt = prompt_response.choices[0].message.content.strip()
            prompt_span.set_attribute(SpanAttributes.OUTPUT_VALUE, video_prompt)

        # ── PHASE 2: Generate video with Veo 2 ───────────────────────────────
        video_url = None
        video_bytes = None

        with tracer.start_as_current_span("veo-video-generation") as veo_span:
            veo_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "TOOL")
            veo_span.set_attribute("tool.name", "veo-3.1-lite-generate-preview")
            veo_span.set_attribute("tool.duration_seconds", 5)
            veo_span.set_attribute(SpanAttributes.INPUT_VALUE, video_prompt)

            try:
                from google import genai as google_genai
                from google.genai import types as google_types

                google_client = google_genai.Client(
                    api_key=os.environ.get("GOOGLE_API_KEY")
                )

                operation = google_client.models.generate_videos(
                    model="veo-3.1-lite-generate-preview",
                    prompt=video_prompt,
                    config=google_types.GenerateVideosConfig(
                        number_of_videos=1,
                        duration_seconds=5,
                        enhance_prompt=True,
                    ),
                )

                # Poll until complete (Veo is async)
                max_wait = 120  # 2 minutes max
                waited = 0
                while not operation.done and waited < max_wait:
                    time.sleep(10)
                    waited += 10
                    operation = google_client.operations.get(operation)

                if operation.done and operation.response.generated_videos:
                    generated_video = operation.response.generated_videos[0].video
                    if hasattr(generated_video, 'uri'):
                        video_url = generated_video.uri
                    elif hasattr(generated_video, 'video_bytes'):
                        video_bytes = generated_video.video_bytes

                    veo_span.set_attribute("tool.status", "success")
                    veo_span.set_attribute(SpanAttributes.OUTPUT_VALUE, video_url or "video_bytes_generated")
                else:
                    veo_span.set_attribute("tool.status", "timeout")

            except Exception as e:
                veo_span.set_attribute("tool.status", "error")
                veo_span.set_attribute("tool.error", str(e))

        # ── PHASE 3: Generate social caption ─────────────────────────────────
        with tracer.start_as_current_span("caption-generation") as caption_span:
            caption_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "LLM")
            caption_span.set_attribute(SpanAttributes.LLM_MODEL_NAME, "gpt-4o-mini")

            caption_input = f"""Write a social media caption for this campaign.

Brand: {brand_name} — sustainable activewear
Tagline: {strategy.tagline}
Key messages: {', '.join(strategy.key_messages[:3])}
Platform: Instagram / TikTok

Requirements:
- 2-3 sentences max
- Authentic, not corporate
- End with a call to action
- Include 5-7 relevant hashtags on a new line
- Only use verified brand claims — no greenwashing

Return caption then hashtags on separate line."""

            caption_span.set_attribute(SpanAttributes.INPUT_VALUE, caption_input)

            caption_response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": caption_input}],
                temperature=0.5,
                max_tokens=200,
            )

            caption_raw = caption_response.choices[0].message.content.strip()
            caption_parts = caption_raw.split("\n\n")
            caption_text = caption_parts[0] if caption_parts else caption_raw
            hashtag_line = caption_parts[1] if len(caption_parts) > 1 else ""
            hashtags = [h.strip() for h in hashtag_line.split() if h.startswith("#")]

            caption_span.set_attribute(SpanAttributes.OUTPUT_VALUE, caption_raw)

        # ── Final span attributes ─────────────────────────────────────────────
        span.set_attribute("trust.pipeline_completed", True)
        span.set_attribute("creative.video_generated", video_url is not None or video_bytes is not None)
        span.set_attribute("creative.model", "veo-3.1-lite-generate-preview")

        return CreativeResult(
            status="APPROVED",
            campaign_concept=strategy.campaign_concept,
            tagline=strategy.tagline,
            video_url=video_url,
            video_bytes=video_bytes,
            video_prompt=video_prompt,
            caption=caption_text,
            hashtags=hashtags,
            halt_reason=None,
            trust_score_inherited=strategy.trust_score_inherited,
            span_id=_get_span_id(span),
        )


def _halted_result(strategy, halt_reason, span) -> CreativeResult:
    span.set_attribute(SpanAttributes.OUTPUT_VALUE, "PIPELINE_HALTED")
    return CreativeResult(
        status="HALTED",
        campaign_concept=strategy.campaign_concept,
        tagline=strategy.tagline,
        video_url=None,
        video_bytes=None,
        video_prompt=None,
        caption=None,
        hashtags=None,
        halt_reason=halt_reason,
        trust_score_inherited=strategy.trust_score_inherited,
        span_id=_get_span_id(span),
    )


def _get_span_id(span) -> Optional[str]:
    ctx = span.get_span_context()
    return format(ctx.span_id, "016x") if ctx else None
