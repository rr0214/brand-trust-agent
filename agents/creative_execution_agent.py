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
"""

import os
import time
import json
import base64
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI
from opentelemetry.trace import get_tracer

from agents.campaign_strategy_agent import CampaignStrategy

tracer = get_tracer("creative-execution-agent", "1.0.0")

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
    video_url: Optional[str]             # Veo generated video URL
    video_bytes: Optional[bytes]         # Raw video bytes if URL not available
    video_prompt: Optional[str]          # Prompt used to generate video
    caption: Optional[str]              # Social media caption
    hashtags: Optional[list]            # Suggested hashtags
    halt_reason: Optional[str]          # Why pipeline halted (if applicable)
    video_error: Optional[str]          # Actual error from Veo API if generation failed
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
    with tracer.start_as_current_span("creative-execution-agent") as span:
        span.set_attribute("openinference.span.kind", "CHAIN")
        span.set_attribute("input.value", strategy.campaign_concept)

        openai_client = OpenAI()

        # ── TRUST GATE ────────────────────────────────────────────────────────
        if strategy.hallucination_detected:
            halt_reason = (
                "Pipeline halted: prohibited brand claims detected in campaign strategy. "
                "No creative assets will be generated from unverified content. "
                "This prevents brand misrepresentation and potential legal liability."
            )
            span.set_attribute("output.value", "PIPELINE_HALTED: " + halt_reason)
            return _halted_result(strategy, halt_reason)

        if strategy.trust_score_inherited < CRITICAL_TRUST_THRESHOLD:
            halt_reason = (
                f"Pipeline halted: grounding score ({strategy.trust_score_inherited:.2f}) "
                f"below critical threshold ({CRITICAL_TRUST_THRESHOLD}). "
                "Campaign strategy lacks sufficient brand evidence. "
                "Expand retrieval corpus before proceeding to creative execution."
            )
            span.set_attribute("output.value", "PIPELINE_HALTED: " + halt_reason)
            return _halted_result(strategy, halt_reason)

        # ── PHASE 1: Build brand-safe video prompt ────────────────────────────
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

        prompt_response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt_input}],
            temperature=0.6,
            max_tokens=200,
        )

        video_prompt = prompt_response.choices[0].message.content.strip()

        # ── PHASE 2: Generate video with Veo 3.1 Lite ────────────────────────
        video_url = None
        video_bytes = None
        veo_error = None

        with tracer.start_as_current_span("veo-video-generation") as veo_span:
            veo_span.set_attribute("openinference.span.kind", "TOOL")
            veo_span.set_attribute("input.value", video_prompt)

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

                    # Prefer raw bytes; if only a URI is returned, download it
                    if hasattr(generated_video, 'video_bytes') and generated_video.video_bytes:
                        video_bytes = generated_video.video_bytes
                    elif hasattr(generated_video, 'uri') and generated_video.uri:
                        uri = generated_video.uri
                        # Google API URIs require the API key for download
                        import requests as _requests
                        api_key = os.environ.get("GOOGLE_API_KEY", "")
                        dl = _requests.get(
                            uri,
                            headers={"x-goog-api-key": api_key},
                            timeout=30,
                        )
                        dl.raise_for_status()
                        video_bytes = dl.content
                        video_url = uri

                veo_span.set_attribute("output.value", video_url or "video_bytes_generated" if (video_url or video_bytes) else "no_video")

            except Exception as e:
                video_bytes = None
                video_url = None
                veo_error = str(e)
                veo_span.set_attribute("output.value", f"error: {veo_error}")

        # ── PHASE 3: Generate social caption ─────────────────────────────────
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

        span.set_attribute("output.value", caption_text or "")

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
            video_error=veo_error,
            trust_score_inherited=strategy.trust_score_inherited,
            span_id=None,
        )


def _halted_result(strategy, halt_reason) -> CreativeResult:
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
        video_error=None,
        trust_score_inherited=strategy.trust_score_inherited,
        span_id=None,
    )
