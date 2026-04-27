"""
Campaign Studio — Brand-safe campaign generation
Three trust-aware AI agents · Instrumented with Arize AX
"""

import io
import os
import time
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Campaign Studio",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Arize tracing
# ---------------------------------------------------------------------------
@st.cache_resource
def init_tracing():
    try:
        from instrumentation.arize_setup import setup_arize_tracing
        setup_arize_tracing()
        return True, None
    except Exception as e:
        return False, str(e)

tracing_ok, tracing_error = init_tracing()

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

h1, h2, h3 { font-family: 'DM Sans', sans-serif; font-weight: 700; }

.studio-title {
    font-family: 'DM Serif Display', serif;
    font-size: 5.5rem;
    font-weight: 400;
    color: #f97316;
    text-align: center;
    margin: 1.5rem 0 0 0;
    line-height: 1;
}

section.main > div { max-width: 780px; margin: 0 auto; padding: 0 2rem; }

.main-header {
    padding: 2rem 0 1rem 0;
}
.tagline-output {
    font-size: 2rem;
    font-weight: 700;
    color: #1a1a1a;
    line-height: 1.2;
    margin: 1rem 0 0.5rem 0;
}
.concept-output {
    font-size: 1rem;
    color: #4b5563;
    line-height: 1.6;
    margin-bottom: 1.5rem;
}
.example-chip {
    display: inline-block;
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-radius: 20px;
    padding: 6px 14px;
    font-size: 0.82rem;
    color: #475569;
    cursor: pointer;
    margin: 4px 4px 4px 0;
    transition: all 0.15s;
}
.example-chip:hover { background: #e2e8f0; color: #1e293b; }
.result-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 16px;
}
.trust-high   { color: #16a34a; font-weight: 700; }
.trust-medium { color: #d97706; font-weight: 700; }
.trust-low    { color: #dc2626; font-weight: 700; }
.halted-card {
    background: #fdf4ff;
    border: 1.5px solid #c084fc;
    border-radius: 12px;
    padding: 24px;
}
.step-label {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: #94a3b8;
    margin-bottom: 4px;
}
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 700;
}
.badge-green  { background: #dcfce7; color: #166534; }
.badge-yellow { background: #fef9c3; color: #713f12; }
.badge-red    { background: #fee2e2; color: #991b1b; }
.badge-purple { background: #f3e8ff; color: #6b21a8; }

div[data-testid="stSidebar"] { background: #f8fafc; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar — pipeline status + demo mode (secondary)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Pipeline Status")
    pipeline_status = st.empty()
    pipeline_status.caption("Run a campaign to see agent activity here.")

    st.markdown("---")
    st.markdown("### ⚙️ Settings")

    FAILURE_CONFIGS = {
        "✅ Normal run": {
            "include_poisoned": False, "simulate_low_confidence": False, "trust_aware": True,
        },
        "⚠️ Trust gap (silent failure)": {
            "include_poisoned": False, "simulate_low_confidence": True, "trust_aware": False,
        },
        "🔴 Prompt injection": {
            "include_poisoned": True, "simulate_low_confidence": False, "trust_aware": False,
        },
        "🛡️ Trust-aware mode (the fix)": {
            "include_poisoned": True, "simulate_low_confidence": False, "trust_aware": True,
        },
    }

    failure_mode = st.segmented_control(
        "Demo scenario",
        options=list(FAILURE_CONFIGS.keys()),
        default="✅ Normal run",
    )
    config = FAILURE_CONFIGS[failure_mode]

    if failure_mode != "✅ Normal run":
        st.caption({
            "⚠️ Trust gap (silent failure)": "Agent 2 never sees Agent 1's low confidence. Claims drift without anyone knowing.",
            "🔴 Prompt injection": "A hidden instruction in a brand doc hijacks the output.",
            "🛡️ Trust-aware mode (the fix)": "Trust signals propagate end-to-end. Injection triggers a halt.",
        }[failure_mode])

    st.markdown("---")
    arize_space_id = os.environ.get("ARIZE_SPACE_ID", "")
    arize_url = f"https://app.arize.com/organizations/{arize_space_id}" if arize_space_id else "https://app.arize.com"
    st.markdown(f"[Open Arize AX ↗]({arize_url})")
    st.caption("Projects → brand-trust-agent → Traces")
    if tracing_ok:
        st.success("Arize connected", icon="📡")
    else:
        st.warning("Arize offline — add API keys", icon="⚠️")

    st.markdown("---")
    with st.expander("📚 Brand document index", expanded=False):
        st.caption("The source documents Agent 1 searches. These are the ground truth for every brand claim.")
        docs = ["verdant_brand_guide.txt", "verdant_products.txt", "verdant_sustainability.txt"]
        if config["include_poisoned"]:
            docs.append("verdant_poisoned.txt ⚠️")
        for d in docs:
            st.markdown(f"{'🔴' if 'poisoned' in d else '🟢'} `{d}`")

        try:
            from agents.brand_research_agent import _get_collection
            coll = _get_collection(include_poisoned=config["include_poisoned"])
            st.caption(f"{coll.count()} chunks indexed")
        except:
            pass

    with st.expander("❓ How it works", expanded=False):
        st.markdown("""
**Three agents run in sequence:**

1. **Research** — searches Verdant brand documents, calculates a grounding score (how well the answer is supported by real sources)

2. **Strategy** — builds the campaign concept and validates every claim against brand policy before using it. Prohibited claims are blocked.

3. **Creative** — if the strategy is clean, generates a Veo 2 social video + caption. If not, the pipeline halts.

**The trust gate** prevents any creative content from being generated from unverified brand claims — not just flagged after the fact.

All steps are traced in **Arize AX** with full span visibility.
        """)

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.markdown("<p style='font-family:DM Serif Display, serif; font-size:1.8rem; font-weight:400; color:#ff4b4b; text-align:center; margin:1.5rem 0 0 0;'>Campaign Studio</p>", unsafe_allow_html=True)
st.markdown("<p style='font-size:1.15rem; color:#64748b; text-align:center; margin-top:8px; margin-bottom:2rem;'>Brand-safe social media campaign generation</p>", unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# Campaign input — center stage
# ---------------------------------------------------------------------------
st.markdown("<h2 style='font-size:1.3rem; font-weight:700; margin-bottom:4px; text-align:center;'>What would you like to campaign about?</h2>", unsafe_allow_html=True)
st.markdown("<p style='font-size:0.95rem; color:#64748b; margin-bottom:1.5rem; text-align:center;'>Describe the goal, audience, and angle. The agents will research brand facts, build the strategy, validate every claim, and generate a social video.</p>", unsafe_allow_html=True)

# Example prompts — clickable
EXAMPLES = [
    "Spring launch · Gen Z runners · recycled materials + trail performance",
    "Summer re-engagement · lapsed customers · sustainability values",
    "New trail line · outdoor enthusiasts · environmental impact",
    "Holiday gifting · performance-conscious parents · sustainable options",
]

st.markdown("**Start with an example**")
selected_example = st.pills(
    "Examples",
    EXAMPLES,
    label_visibility="collapsed",
)
if selected_example:
    st.session_state["user_prompt"] = selected_example

user_prompt = st.text_area(
    "Campaign brief",
    value=st.session_state.get("user_prompt", ""),
    height=110,
    placeholder="e.g. Spring collection launch targeting Gen Z runners — lead with our recycled materials story and performance credentials",
    label_visibility="collapsed",
)

run_btn = st.button("▶  Generate Campaign", type="primary", use_container_width=False)

# ---------------------------------------------------------------------------
# Pipeline output
# ---------------------------------------------------------------------------
if run_btn and user_prompt.strip():
    from agents.brand_research_agent import run_brand_research
    from agents.campaign_strategy_agent import run_campaign_strategy
    from agents.creative_execution_agent import run_creative_execution

    st.divider()

    research_query = f"What brand facts, certifications, and approved claims support this campaign: {user_prompt}"

    # ── AGENT 1 ───────────────────────────────────────────────────────────
    with st.status("🔍 Researching brand facts...", expanded=True) as s1:
        pipeline_status.markdown("**Step 1 of 3** — Brand Research")
        t0 = time.time()
        research = run_brand_research(
            query=research_query,
            include_poisoned=config["include_poisoned"],
            simulate_low_confidence=config["simulate_low_confidence"],
        )
        t1 = time.time()

        gs = research.grounding_score
        score_class = "trust-high" if gs >= 0.70 else "trust-medium" if gs >= 0.50 else "trust-low"
        score_label = "Strong" if gs >= 0.70 else "Moderate" if gs >= 0.50 else "Weak"

        st.markdown(f"**Brand grounding:** <span class='{score_class}'>{score_label} ({gs:.2f})</span>", unsafe_allow_html=True)
        st.markdown(f"{research.answer}")
        st.caption(f"Sources: {', '.join(research.sources)} · {(t1-t0):.1f}s")

        if config["include_poisoned"]:
            st.error("🔴 Injection document detected in retrieval")
        if config["simulate_low_confidence"] and gs < 0.6:
            st.warning(f"⚠️ Low grounding ({gs:.2f}) — Agent 2 will not be informed in this scenario")

        s1.update(label=f"✅ Brand research complete — grounding {gs:.2f}", state="complete", expanded=False)

    # Update sidebar pipeline status
    with pipeline_status.container():
        st.markdown("**Agent 1** ✅ Brand Research")
        st.progress(0.33)

    # ── AGENT 2 ───────────────────────────────────────────────────────────
    with st.status("📣 Building campaign strategy...", expanded=True) as s2:
        pipeline_status.markdown("**Step 2 of 3** — Campaign Strategy")
        t2 = time.time()
        strategy = run_campaign_strategy(
            research=research,
            campaign_brief=user_prompt,
            trust_aware=config["trust_aware"],
        )
        t3 = time.time()

        if strategy.hallucination_detected:
            st.error("🚨 Prohibited claims detected in output — pipeline will halt at creative step")
        elif not config["trust_aware"] and research.grounding_score < 0.65:
            st.warning("⚠️ Strategy generated without grounding context — claims may be unsupported")
        else:
            st.success("✅ All claims validated against brand policy")

        st.caption(f"{(t3-t2):.1f}s · {len(strategy.key_messages)} key messages · {len(strategy.risk_flags)} risk flags")

        s2.update(
            label=f"{'🚨 Strategy flagged — prohibited claims' if strategy.hallucination_detected else '✅ Campaign strategy ready'}",
            state="error" if strategy.hallucination_detected else "complete",
            expanded=False
        )

    with pipeline_status.container():
        st.markdown("**Agent 1** ✅ Brand Research")
        st.markdown("**Agent 2** ✅ Campaign Strategy")
        st.progress(0.66)

    # ── AGENT 3 ───────────────────────────────────────────────────────────
    with st.status("🎬 Generating creative...", expanded=True) as s3:
        pipeline_status.markdown("**Step 3 of 3** — Creative Execution")
        t4 = time.time()
        creative = run_creative_execution(strategy=strategy, brand_name="Verdant")
        t5 = time.time()

        if creative.status == "HALTED":
            s3.update(label="🛑 Creative halted — trust gate fired", state="error", expanded=False)
        else:
            s3.update(label="✅ Creative package ready", state="complete", expanded=False)

    with pipeline_status.container():
        st.markdown("**Agent 1** ✅ Brand Research")
        st.markdown("**Agent 2** ✅ Campaign Strategy")
        if creative.status == "HALTED":
            st.markdown("**Agent 3** 🛑 Halted")
            st.progress(1.0)
        else:
            st.markdown("**Agent 3** ✅ Creative Execution")
            st.progress(1.0)
        st.caption(f"Total: {(t5-t0):.1f}s")
        st.markdown(f"[View trace in Arize AX ↗]({arize_url})")

    # ── Results ───────────────────────────────────────────────────────────
    st.divider()

    if creative.status == "HALTED":
        st.markdown(f"""
        <div class='halted-card'>
            <div class='step-label'>Pipeline halted</div>
            <h3 style='color:#7c3aed; margin:8px 0;'>🛑 Content generation stopped</h3>
            <p style='color:#4b5563;'>{creative.halt_reason}</p>
            <p style='color:#94a3b8; font-size:0.85rem;'>No video or caption was generated. This is intentional — the trust gate prevents brand-unsafe content from being created, not just flagged after the fact. The halt event is fully recorded in Arize AX.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("**Recommended next steps**")
        if strategy.hallucination_detected:
            actions = [
                ("🛑 Do not publish", "Contains prohibited claims — do not deliver to any downstream system."),
                ("👤 Escalate to brand safety team", "Flag for manual review within 1 business hour."),
                ("🔒 Quarantine source document", "Remove flagged chunk from active index. Source: `verdant_poisoned.txt`."),
                ("📋 Create audit record", f"Log span_id, injection_risk=HIGH, action=HALTED — required for EU AI Act Article 13."),
            ]
        else:
            actions = [
                ("⚠️ Do not auto-publish", "Confidence too low — flag as LOW_CONFIDENCE before any use."),
                ("🔄 Retry with expanded sources", "Increase retrieval top-k and run again."),
                ("👤 Human review required", "Route to brand reviewer before any customer-facing use."),
                ("📋 Create audit record", f"Log span_id, grounding_score=LOW, action=FLAGGED — required for SOC 2 CC7.2."),
            ]
        for action, detail in actions:
            st.markdown(f"**{action}** — {detail}")

    else:
        # ── Campaign output ────────────────────────────────────────────────

        # Purpose + description at the top
        st.markdown(f"<div class='tagline-output'>\"{strategy.tagline}\"</div>", unsafe_allow_html=True)

        col_meta1, col_meta2 = st.columns(2)
        with col_meta1:
            st.markdown("<div class='step-label'>Campaign Purpose</div>", unsafe_allow_html=True)
            # Pull first key message as the purpose — the "why" of the campaign
            purpose = strategy.key_messages[0] if strategy.key_messages else strategy.campaign_concept
            st.markdown(f"<div style='font-size:0.95rem; color:#374151; line-height:1.6;'>{purpose}</div>", unsafe_allow_html=True)
        with col_meta2:
            st.markdown("<div class='step-label'>Campaign Description</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:0.95rem; color:#374151; line-height:1.6;'>{strategy.campaign_concept}</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        col_left, col_right = st.columns([3, 2])

        with col_left:
            # Video
            st.markdown("<div class='step-label'>Social Video</div>", unsafe_allow_html=True)
            if creative.video_bytes:
                st.video(io.BytesIO(creative.video_bytes), format="video/mp4")
            elif creative.video_url:
                st.video(creative.video_url)
            else:
                if creative.video_error:
                    st.warning(f"⚠️ Video generation failed: `{creative.video_error}`")
                else:
                    st.markdown("""
                <div style='background:#f1f5f9; border-radius:10px; padding:40px; text-align:center; color:#64748b;'>
                    <div style='font-size:2rem;'>📽️</div>
                    <div style='font-weight:600; margin-top:8px;'>Veo 3.1 Lite ready to generate</div>
                    <div style='font-size:0.85rem; margin-top:4px;'>Add a Google API key to generate the video</div>
                </div>
                    """, unsafe_allow_html=True)

            if creative.video_prompt:
                with st.expander("Video prompt", expanded=False):
                    st.markdown(f"*{creative.video_prompt}*")

        with col_right:
            # Caption
            st.markdown("<div class='step-label'>Caption</div>", unsafe_allow_html=True)
            if creative.caption:
                st.markdown(f"""
                <div style='background:#f8fafc; border-radius:10px; padding:16px; font-size:0.95rem; line-height:1.6; color:#1e293b;'>
                {creative.caption}
                </div>
                """, unsafe_allow_html=True)

            if creative.hashtags:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("<div class='step-label'>Hashtags</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='color:#475569; font-size:0.9rem;'>{' '.join(creative.hashtags)}</div>", unsafe_allow_html=True)

            if len(strategy.key_messages) > 1:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("<div class='step-label'>Key Messages</div>", unsafe_allow_html=True)
                for msg in strategy.key_messages[1:]:
                    st.markdown(f"<div style='padding:6px 0; border-bottom:1px solid #f1f5f9; font-size:0.9rem; color:#374151;'>→ {msg}</div>", unsafe_allow_html=True)

        # Trust signals (collapsed)
        st.markdown("---")
        with st.expander("🔬 Trust signals (Arize AX span attributes)", expanded=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**Agent 1**")
                st.code(f"grounding_score: {research.grounding_score:.2f}\ninjection_risk: {research.confidence_metadata.get('injection_risk','none').upper()}")
            with c2:
                st.markdown("**Agent 2**")
                st.code(f"score_inherited: {strategy.trust_score_inherited:.2f}\ntrust_aware: {strategy.trust_aware_mode}\nhallucination: {strategy.hallucination_detected}")
            with c3:
                st.markdown("**Agent 3**")
                st.code(f"pipeline_halted: {creative.status == 'HALTED'}\nvideo_generated: {bool(creative.video_url or creative.video_bytes)}")

            if not config["trust_aware"]:
                st.warning("⚠️ Trust gap visible: Agent 1's grounding score is in its span, but Agent 2 received no trust context. This is the gap Arize Sentinel closes.")

        st.markdown(f"[View full trace in Arize AX ↗]({arize_url})")

elif run_btn and not user_prompt.strip():
    st.warning("Please describe your campaign before generating.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption("Campaign Studio · Arize AX trust observability · Built by Rebecca Riggs · 2026")
