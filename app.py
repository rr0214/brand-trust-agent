"""
Brand Trust Agent — Streamlit App
====================================
A three-agent pipeline that keeps brand campaigns accurate, safe, and on-brand.

Run: streamlit run app.py
"""

import os
import time
from dotenv import load_dotenv

load_dotenv()

import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Verdant Campaign Studio",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Initialize Arize tracing
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
.trust-high   { color: #22c55e; font-weight: 700; }
.trust-medium { color: #f59e0b; font-weight: 700; }
.trust-low    { color: #ef4444; font-weight: 700; }
.badge-success { background: #dcfce7; color: #166534; padding: 2px 10px; border-radius: 12px; font-size: 0.78em; font-weight: 700; }
.badge-warn    { background: #fef9c3; color: #713f12; padding: 2px 10px; border-radius: 12px; font-size: 0.78em; font-weight: 700; }
.badge-danger  { background: #fee2e2; color: #991b1b; padding: 2px 10px; border-radius: 12px; font-size: 0.78em; font-weight: 700; }
.badge-halted  { background: #f3e8ff; color: #6b21a8; padding: 2px 10px; border-radius: 12px; font-size: 0.78em; font-weight: 700; }
.pipeline-step { border-left: 3px solid #40916c; padding-left: 14px; margin-bottom: 8px; }
.halted-box    { background: #fdf4ff; border: 1px solid #c084fc; border-radius: 8px; padding: 16px; margin-top: 8px; }
.hero-input    { font-size: 1rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar — Demo Mode only (secondary, for interview)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🔬 Demo Mode")
    st.caption("Simulate trust failure scenarios to show what Arize AX catches — and what it misses today.")

    failure_mode = st.radio(
        "Scenario",
        options=[
            "✅ Normal",
            "⚠️ Trust Propagation Failure",
            "🔴 Prompt Injection Attack",
            "🛡️ Trust-Aware Mode (the fix)",
        ],
        index=0,
    )

    FAILURE_CONFIGS = {
        "✅ Normal": {
            "include_poisoned": False, "simulate_low_confidence": False, "trust_aware": True,
            "badge": "success",
            "desc": "Clean run. All three agents complete. Campaign + video delivered.",
        },
        "⚠️ Trust Propagation Failure": {
            "include_poisoned": False, "simulate_low_confidence": True, "trust_aware": False,
            "badge": "warn",
            "desc": "Agent 1 retrieves thin evidence. Agent 2 is never told. Confident claims from weak sources.",
        },
        "🔴 Prompt Injection Attack": {
            "include_poisoned": True, "simulate_low_confidence": False, "trust_aware": False,
            "badge": "danger",
            "desc": "Adversarial instructions hidden in a brand doc hijack Agent 2. Agent 3 trust gate fires.",
        },
        "🛡️ Trust-Aware Mode (the fix)": {
            "include_poisoned": True, "simulate_low_confidence": False, "trust_aware": True,
            "badge": "success",
            "desc": "Trust signals propagate end-to-end. Injection triggers full pipeline halt.",
        },
    }
    config = FAILURE_CONFIGS[failure_mode]
    badge_map = {
        "success": '<span class="badge-success">✓ Expected</span>',
        "warn":    '<span class="badge-warn">⚠ Silent failure</span>',
        "danger":  '<span class="badge-danger">✗ Security failure</span>',
    }
    st.markdown(badge_map[config["badge"]], unsafe_allow_html=True)
    st.caption(config["desc"])

    st.markdown("---")
    arize_space_id = os.environ.get("ARIZE_SPACE_ID", "")
    arize_url = f"https://app.arize.com/organizations/{arize_space_id}" if arize_space_id else "https://app.arize.com"
    st.markdown(f"[Open Arize AX ↗]({arize_url})")
    st.caption("Projects → brand-trust-agent → Traces")
    st.markdown("---")
    if tracing_ok:
        st.success("📡 Arize AX live")
    else:
        st.warning("Arize offline — add API keys")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
col_logo, col_title = st.columns([1, 11])
with col_logo:
    st.markdown("# 🌿")
with col_title:
    st.markdown("# Verdant Campaign Studio")
    st.caption("Describe what you want to promote — we'll research brand facts, build a strategy, validate every claim, and generate a social video.")

st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_campaign, tab_index = st.tabs(["🌿  Campaign", "📚  Index Explorer"])

# ===========================================================================
# CAMPAIGN TAB
# ===========================================================================
with tab_campaign:

    # ── Single natural-language input ─────────────────────────────────────
    user_prompt = st.text_area(
        "What would you like to campaign about?",
        value="Verdant wants to promote its spring activewear collection to Gen Z runners. Lead with the sustainability story and performance credentials.",
        height=100,
        placeholder="e.g. Verdant wants to launch a summer collection targeting millennial hikers. Focus on recycled materials and trail performance.",
        help="Describe the brand, audience, and campaign goal in plain English. The three agents will handle the rest."
    )

    run_btn = st.button("▶  Generate Campaign", type="primary")

    with st.expander("How does this work?", expanded=False):
        st.markdown("""
**Three AI agents run in sequence — each one checks the previous one's work.**

1. **Agent 1 — Brand Research** searches Verdant's brand documents to find verified facts, certifications, and claims that apply to your campaign goal.

2. **Agent 2 — Campaign Strategy** builds a campaign concept, tagline, and key messages — but before including any specific claim or statistic, it calls a brand policy checker to confirm it's approved. Prohibited claims (e.g. "carbon neutral", "B Corp certified") are flagged and removed.

3. **Agent 3 — Creative Execution** has a trust gate: if the strategy contains any unverified claims, the pipeline stops here. Otherwise it writes a Veo 2 video prompt, generates a 5-second social media video, and writes a caption with hashtags.

All three agents are fully traced in **Arize AX** — every LLM call, tool call, and trust signal is captured as a span.
        """)

    st.divider()

    if not run_btn:
        st.markdown("""
        <div style='text-align:center; padding: 48px 0; color: #94a3b8;'>
            <div style='font-size: 2rem; margin-bottom: 10px;'>🌿</div>
            <div style='font-size: 1rem; font-weight: 600; margin-bottom: 6px;'>Ready when you are</div>
            <div style='font-size: 0.9rem;'>Describe your campaign above, then click <strong>Generate Campaign</strong></div>
        </div>
        """, unsafe_allow_html=True)

    # ── Run pipeline ──────────────────────────────────────────────────────
    if run_btn:
        from agents.brand_research_agent import run_brand_research
        from agents.campaign_strategy_agent import run_campaign_strategy
        from agents.creative_execution_agent import run_creative_execution

        # Derive research query from the user's prompt automatically
        # Agent 1 uses this to search the vector store
        research_query = f"What brand facts, certifications, and approved claims support this campaign: {user_prompt}"

        # ── AGENT 1 ───────────────────────────────────────────────────────
        st.markdown("#### 🔍 Step 1 of 3 — Researching brand facts")
        with st.spinner("Agent 1 is searching Verdant brand documents for verified claims..."):
            t0 = time.time()
            research = run_brand_research(
                query=research_query,
                include_poisoned=config["include_poisoned"],
                simulate_low_confidence=config["simulate_low_confidence"],
            )
            t1 = time.time()

        gs = research.grounding_score
        score_class = "trust-high" if gs >= 0.70 else "trust-medium" if gs >= 0.50 else "trust-low"
        score_label = "HIGH" if gs >= 0.70 else "MEDIUM" if gs >= 0.50 else "LOW"

        with st.container():
            col_r1, col_r2 = st.columns([3, 1])
            with col_r1:
                st.markdown(f"<div class='pipeline-step'><strong>Brand research:</strong> {research.answer}</div>", unsafe_allow_html=True)
                st.caption(f"Sources: {', '.join(research.sources)} · {(t1-t0):.1f}s · Agent 1 span in Arize AX")
            with col_r2:
                st.markdown(f"**Brand grounding:** <span class='{score_class}'>{gs:.2f} / 1.0 ({score_label})</span>", unsafe_allow_html=True)
                inj = research.confidence_metadata.get("injection_risk", "none")
                if inj == "high":
                    st.error(f"🔴 Injection risk: HIGH")
                else:
                    st.success(f"✅ Injection risk: NONE")

        if config["include_poisoned"]:
            st.error("🔴 Demo: An adversarial document was included in retrieval — hidden instructions may have been passed to Agent 2.")
        if config["simulate_low_confidence"] and gs < 0.6:
            st.warning(f"⚠️ Demo: Low grounding score ({gs:.2f}). In failure mode, Agent 2 won't know this and may make up claims.")

        st.divider()

        # ── AGENT 2 ───────────────────────────────────────────────────────
        st.markdown("#### 📣 Step 2 of 3 — Building campaign strategy")
        with st.spinner("Agent 2 is building your campaign and validating every claim against brand policy..."):
            t2 = time.time()
            strategy = run_campaign_strategy(
                research=research,
                campaign_brief=user_prompt,
                trust_aware=config["trust_aware"],
            )
            t3 = time.time()

        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            st.markdown(f"### \"{strategy.tagline}\"")
            st.markdown(f"{strategy.campaign_concept}")
            if strategy.key_messages:
                st.markdown("**Key messages:**")
                for msg in strategy.key_messages:
                    st.markdown(f"- {msg}")
            if strategy.channel_recommendations:
                st.markdown("**Recommended channels:**")
                for ch in strategy.channel_recommendations:
                    st.markdown(f"- {ch}")
        with col_s2:
            st.caption(f"{(t3-t2):.1f}s · Agent 2 span in Arize AX")
            if strategy.hallucination_detected:
                st.error("🚨 Prohibited claims detected — pipeline will halt at Agent 3")
            elif not config["trust_aware"] and research.grounding_score < 0.65:
                st.warning("⚠️ Operating without grounding context")
            else:
                st.success("✅ Claims validated against brand policy")

        if strategy.risk_flags:
            for flag in strategy.risk_flags:
                st.warning(f"⚠️ Brand policy flag: {flag}")

        st.divider()

        # ── AGENT 3 ───────────────────────────────────────────────────────
        st.markdown("#### 🎬 Step 3 of 3 — Creating social content")
        with st.spinner("Agent 3 is generating your video and caption..."):
            t4 = time.time()
            creative = run_creative_execution(strategy=strategy, brand_name="Verdant")
            t5 = time.time()

        if creative.status == "HALTED":
            st.markdown(f"""
            <div class='halted-box'>
                <strong style='color:#7c3aed;'>🛑 Content generation stopped</strong><br><br>
                {creative.halt_reason}<br><br>
                <em>No video or caption was generated. This is intentional — the trust gate prevents
                brand-unsafe content from ever being created, not just flagged after the fact.</em>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("**What should happen next?**")
            st.caption("These are the actions Arize Sentinel would recommend automatically based on your configured compliance framework.")

            if strategy.hallucination_detected:
                actions = [
                    ("🛑 Do not publish", "This output contains prohibited claims and must not be delivered to any downstream system or user."),
                    ("👤 Escalate to brand safety team", "Flag for manual review within 1 business hour."),
                    ("🔒 Quarantine the source document", "The flagged chunk should be removed from the active index pending investigation."),
                    ("📋 Create audit record", f"Log `span_id={creative.span_id}`, `injection_risk=HIGH`, `action=HALTED` — required for EU AI Act Article 13 transparency."),
                ]
            else:
                actions = [
                    ("⚠️ Do not auto-publish", "Output confidence is too low. Flag as `LOW_CONFIDENCE` before any use."),
                    ("🔄 Retry with more sources", "Expand the retrieval corpus and run again."),
                    ("👤 Human review required", "Route to a brand reviewer before any customer-facing use."),
                    ("📋 Create audit record", f"Log `span_id={creative.span_id}`, `grounding_score=LOW`, `action=FLAGGED` — required for SOC 2 CC7.2."),
                ]
            for action, detail in actions:
                st.markdown(f"**{action}** — {detail}")

        else:
            col_v, col_c = st.columns([3, 2])
            with col_v:
                st.markdown("**Your social video**")
                if creative.video_url:
                    st.video(creative.video_url)
                    st.caption("Generated by Veo 2 · 5 seconds · Brand-safe")
                elif creative.video_bytes:
                    st.video(creative.video_bytes)
                    st.caption("Generated by Veo 2 · 5 seconds · Brand-safe")
                else:
                    st.info("Veo 2 video generation requires a Google API key. The prompt below was built and is ready to send.", icon="📽️")

                if creative.video_prompt:
                    with st.expander("Video prompt (built for Veo 2)", expanded=not (creative.video_url or creative.video_bytes)):
                        st.markdown(f"*{creative.video_prompt}*")
                        st.caption("Engineered to Verdant visual guidelines: forest greens, natural light, real people, no text or logos.")

            with col_c:
                if creative.caption:
                    st.markdown("**Your caption**")
                    st.markdown(f"> {creative.caption}")
                if creative.hashtags:
                    st.markdown("**Hashtags**")
                    st.markdown(" ".join(creative.hashtags))
                st.caption(f"Agent 3 · {(t5-t4):.1f}s · Veo 2 · GPT-4o-mini")

            st.success("✅ Campaign complete — all claims verified, content brand-safe")

        # ── Observability panel (collapsed by default) ────────────────────
        st.markdown("---")
        with st.expander("🔬 Arize AX — Trust signals across all three agents", expanded=False):
            col_t1, col_t2, col_t3 = st.columns(3)
            with col_t1:
                st.markdown("**Agent 1 span**")
                st.code(f"trust.grounding_score = {research.grounding_score:.2f}\ntrust.injection_risk = {research.confidence_metadata.get('injection_risk','none').upper()}\nspan.kind = AGENT")
            with col_t2:
                st.markdown("**Agent 2 span**")
                st.code(f"trust.score_inherited = {strategy.trust_score_inherited:.2f}\ntrust.trust_aware = {strategy.trust_aware_mode}\ntrust.hallucination = {strategy.hallucination_detected}\npolicy.prohibited_caught = ...")
            with col_t3:
                st.markdown("**Agent 3 span**")
                status_val = creative.status == 'HALTED'
                vid_val = bool(creative.video_url or creative.video_bytes)
                st.code(f"trust.pipeline_halted = {status_val}\ncreative.video_generated = {vid_val}\nspan_id = {(creative.span_id or 'n/a')[:12]}...")

            if not config["trust_aware"]:
                st.warning("⚠️ **The gap:** Agent 1's grounding score is captured in its span, but Agent 2's span received no trust context. Arize AX shows both spans — but doesn't natively link them. This is what Arize Sentinel closes.")
            else:
                st.success("✅ **Trust-aware mode:** Grounding score and injection risk propagated Agent 1 → 2 → 3 as span attributes.")

        st.markdown(f"🔗 **[View full trace in Arize AX ↗]({arize_url})**")

# ===========================================================================
# INDEX EXPLORER TAB
# ===========================================================================
with tab_index:
    st.markdown("### 📚 Brand Document Index")
    st.caption("The vector store Agent 1 searches. These are Verdant's brand docs — the ground truth for every claim.")

    import pandas as pd
    from agents.brand_research_agent import _get_collection

    col_left, col_right = st.columns([1, 2])
    with col_left:
        include_poison_index = st.checkbox("Include injected document (demo)", value=False,
            help="Adds verdant_poisoned.txt — an adversarial document with hidden instructions.")
        preview_query = st.text_input("Test a retrieval query",
            placeholder="e.g. What sustainability certifications does Verdant have?")
        preview_n = st.slider("Number of results", 1, 8, 4)
        preview_btn = st.button("🔍 Run Retrieval", use_container_width=True)

    with col_right:
        st.markdown("**Documents in index:**")
        for d in ["verdant_brand_guide.txt", "verdant_products.txt", "verdant_sustainability.txt"]:
            st.markdown(f"🟢 `{d}`")
        if include_poison_index:
            st.markdown("🔴 `verdant_poisoned.txt` — contains adversarial instructions")

    st.divider()

    with st.spinner("Loading..."):
        try:
            coll = _get_collection(include_poisoned=include_poison_index)
            all_data = coll.get(include=["documents", "metadatas"])
            rows = [
                {
                    "Source": meta.get("source", "unknown"),
                    "Chunk #": meta.get("chunk_index", i),
                    "Length": len(doc),
                    "Preview": doc[:200].replace("\n", " ") + ("…" if len(doc) > 200 else ""),
                }
                for i, (doc, meta) in enumerate(zip(all_data["documents"], all_data["metadatas"]))
            ]
            df = pd.DataFrame(rows)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total chunks", len(df))
            m2.metric("Documents", df["Source"].nunique())
            m3.metric("Avg chunk length", f"{int(df['Length'].mean())} chars")
            m4.metric("Injection doc", "Loaded ⚠️" if include_poison_index else "Not loaded ✅")

            def highlight_poisoned(row):
                return ["background-color: #fee2e2"] * len(row) if "poisoned" in str(row["Source"]) else [""] * len(row)

            st.dataframe(df.style.apply(highlight_poisoned, axis=1), use_container_width=True, height=400)
        except Exception as e:
            st.error(f"Could not load index: {e}. Make sure OPENAI_API_KEY is set.")

    if preview_btn and preview_query:
        st.divider()
        st.markdown(f"**Results for:** *\"{preview_query}\"*")
        with st.spinner("Searching..."):
            try:
                coll2 = _get_collection(include_poisoned=include_poison_index)
                results = coll2.query(
                    query_texts=[preview_query],
                    n_results=min(preview_n, coll2.count()),
                    include=["documents", "metadatas", "distances"],
                )
                for i, (doc, meta, dist) in enumerate(zip(
                    results["documents"][0], results["metadatas"][0], results["distances"][0]
                )):
                    sim = max(0.0, 1.0 - (dist / 2.0))
                    is_poisoned = "poisoned" in meta.get("source", "")
                    with st.expander(
                        f"{'🔴 INJECTED DOC' if is_poisoned else f'✅ Result {i+1}'} · `{meta.get('source')}` · similarity {sim:.3f}",
                        expanded=i < 2
                    ):
                        score_class = "trust-low" if sim < 0.5 else "trust-medium" if sim < 0.7 else "trust-high"
                        st.markdown(f"<span class='{score_class}'>Relevance: {sim:.3f}</span>", unsafe_allow_html=True)
                        st.text(doc)
                        if is_poisoned:
                            st.error("This chunk contains adversarial instructions that attempt to override Agent 2's system prompt when retrieved.")
            except Exception as e:
                st.error(f"Search failed: {e}")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption("Verdant Campaign Studio · Three-agent pipeline with Arize AX trust observability · Built by Rebecca Riggs · 2026")
