"""
Brand Trust Agent — Streamlit App
====================================
A three-agent pipeline that keeps brand campaigns accurate, safe, and on-brand.
Instrumented with Arize AX for full observability.

Primary use: brand teams use this to generate campaign strategies + creative assets
             with built-in brand safety guardrails.

Demo mode:  shows trust failure scenarios for the Arize AX interview — toggleable
            via a small control in the sidebar.

Run: streamlit run app.py
"""

import os
import time
import base64
from pathlib import Path
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
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Initialize Arize tracing (once per session)
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
/* Brand palette */
:root {
  --verdant-green: #2d6a4f;
  --verdant-light: #40916c;
  --verdant-bg: #d8f3dc;
  --trust-high: #22c55e;
  --trust-med: #f59e0b;
  --trust-low: #ef4444;
}
.trust-high   { color: #22c55e; font-weight: 700; }
.trust-medium { color: #f59e0b; font-weight: 700; }
.trust-low    { color: #ef4444; font-weight: 700; }
.agent-header { font-size: 1.05rem; font-weight: 700; margin-bottom: 4px; }
.badge-success { background: #dcfce7; color: #166534; padding: 2px 10px; border-radius: 12px; font-size: 0.78em; font-weight: 700; }
.badge-warn    { background: #fef9c3; color: #713f12; padding: 2px 10px; border-radius: 12px; font-size: 0.78em; font-weight: 700; }
.badge-danger  { background: #fee2e2; color: #991b1b; padding: 2px 10px; border-radius: 12px; font-size: 0.78em; font-weight: 700; }
.badge-halted  { background: #f3e8ff; color: #6b21a8; padding: 2px 10px; border-radius: 12px; font-size: 0.78em; font-weight: 700; }
.pipeline-step { border-left: 3px solid #40916c; padding-left: 14px; margin-bottom: 8px; }
.halted-box    { background: #fdf4ff; border: 1px solid #c084fc; border-radius: 8px; padding: 16px; margin-top: 8px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
col_logo, col_title, col_status = st.columns([1, 7, 2])
with col_logo:
    st.markdown("## 🌿")
with col_title:
    st.markdown("## Verdant Campaign Studio")
    st.caption("Brand-safe campaign generation · Powered by three trust-aware AI agents")
with col_status:
    if tracing_ok:
        st.success("📡 Arize AX live", icon="✅")
    else:
        st.warning("Arize offline", icon="⚠️")

st.divider()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🌿 Campaign Brief")

    campaign_brief = st.text_area(
        "What's the campaign goal?",
        value="Spring launch targeting Gen Z runners. Lead with sustainability story and performance credentials.",
        height=110,
        help="Agent 2 takes research + this brief to generate the campaign strategy."
    )

    research_query = st.text_input(
        "Brand research question",
        value="What sustainability claims and certifications can we use in a spring campaign?",
        help="Agent 1 will RAG over Verdant brand documents to answer this before building the strategy."
    )

    st.markdown("---")

    # ── Demo Mode ────────────────────────────────────────────────────────────
    # Secondary toggle — shown for interview purposes. In production this
    # section would be hidden or restricted to an admin view.
    with st.expander("🔬 Demo Mode (Trust Failure Scenarios)", expanded=False):
        st.caption("Toggle failure modes to demonstrate how Arize AX surfaces trust gaps in multi-agent pipelines.")
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
                "desc": "Clean run — high-quality retrieval, grounded strategy, creative package delivered.",
            },
            "⚠️ Trust Propagation Failure": {
                "include_poisoned": False, "simulate_low_confidence": True, "trust_aware": False,
                "badge": "warn",
                "desc": "Agent 1 retrieves thin evidence (low grounding). Agent 2 is never told — makes confident claims from weak sources. Agent 3 will halt if the strategy is bad enough.",
            },
            "🔴 Prompt Injection Attack": {
                "include_poisoned": True, "simulate_low_confidence": False, "trust_aware": False,
                "badge": "danger",
                "desc": "Adversarial instructions hidden in a brand doc hijack Agent 2's output — false claims, competitor reference. Agent 3 trust gate fires.",
            },
            "🛡️ Trust-Aware Mode (the fix)": {
                "include_poisoned": True, "simulate_low_confidence": False, "trust_aware": True,
                "badge": "success",
                "desc": "Grounding score + injection risk propagate from Agent 1 → 2 → 3. Low trust triggers hedged output. Injection triggers full halt. This is what Arize Sentinel enforces natively.",
            },
        }
        config = FAILURE_CONFIGS[failure_mode]
        badge_map = {
            "success": '<span class="badge-success">✓ Expected</span>',
            "warn":    '<span class="badge-warn">⚠ Silent failure</span>',
            "danger":  '<span class="badge-danger">✗ Security failure</span>',
        }
        st.markdown(f"{badge_map[config['badge']]} — {config['desc']}", unsafe_allow_html=True)

    # No Demo Mode active → use normal config
    if "config" not in dir():
        config = {
            "include_poisoned": False, "simulate_low_confidence": False, "trust_aware": True,
        }

    st.markdown("---")
    arize_space_id = os.environ.get("ARIZE_SPACE_ID", "")
    arize_url = f"https://app.arize.com/organizations/{arize_space_id}" if arize_space_id else "https://app.arize.com"
    st.markdown(f"[Open Arize AX ↗]({arize_url})")
    st.caption("Projects → brand-trust-agent → Traces")
    st.markdown("---")
    run_btn = st.button("▶  Generate Campaign", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_campaign, tab_index = st.tabs(["🌿  Campaign", "📚  Index Explorer"])

# ---------------------------------------------------------------------------
# CAMPAIGN TAB
# ---------------------------------------------------------------------------
with tab_campaign:

    # ── Pipeline overview ──────────────────────────────────────────────────
    with st.expander("📊 How the pipeline works", expanded=False):
        st.markdown("""
```
Campaign Brief + Research Question
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│  AGENT 1 — Brand Research                                    │
│  ChromaDB vector search → GPT-4o-mini synthesis             │
│  Output: answer + grounding_score (0–1) + injection_risk    │
└──────────────────────────────┬───────────────────────────────┘
                               │ trust signals propagated?  ← THE GAP
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  AGENT 2 — Campaign Strategy                                 │
│  GPT-4o-mini + check_brand_policy() tool                    │
│  Validates every claim before use                            │
│  Output: concept · tagline · key messages · risk flags      │
└──────────────────────────────┬───────────────────────────────┘
                               │ hallucination_detected? → HALT
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  AGENT 3 — Creative Execution              [TRUST GATE 🛡️]   │
│  GPT-4o-mini builds brand-safe video prompt                 │
│  Veo 2 generates 5-second social video                      │
│  GPT-4o-mini writes Instagram/TikTok caption + hashtags     │
│  Output: video · caption · hashtags  OR  pipeline halted    │
└──────────────────────────────────────────────────────────────┘
        │
        ▼
  Arize AX — every span linked, trust metadata propagated
  Agent Visibility shows the full 3-agent flow
```
**The Arize Sentinel proposal** adds a native Trust Layer: grounding scores,
injection risk, and confidence signals flow automatically between agents —
turning Arize from observe-and-react into prevent-and-enforce.
        """)

    if not run_btn:
        st.markdown("""
        <div style='text-align:center; padding: 60px 0; color: #94a3b8;'>
            <div style='font-size: 2.5rem; margin-bottom: 12px;'>🌿</div>
            <div style='font-size: 1.1rem; font-weight: 600; margin-bottom: 8px;'>Ready to generate your campaign</div>
            <div>Fill in your campaign brief in the sidebar, then click <strong>Generate Campaign</strong></div>
        </div>
        """, unsafe_allow_html=True)

    if run_btn:
        from agents.brand_research_agent import run_brand_research
        from agents.campaign_strategy_agent import run_campaign_strategy
        from agents.creative_execution_agent import run_creative_execution

        # ──────────────────────────────────────────────────────────────────
        # AGENT 1
        # ──────────────────────────────────────────────────────────────────
        st.markdown("### 🔍 Agent 1 — Brand Research")
        with st.spinner("Researching Verdant brand documents..."):
            t0 = time.time()
            research = run_brand_research(
                query=research_query,
                include_poisoned=config["include_poisoned"],
                simulate_low_confidence=config["simulate_low_confidence"],
            )
            t1 = time.time()

        gs = research.grounding_score
        if gs >= 0.70:
            score_class, score_label = "trust-high", "HIGH"
        elif gs >= 0.50:
            score_class, score_label = "trust-medium", "MEDIUM"
        else:
            score_class, score_label = "trust-low", "LOW"

        col_a1, col_a2 = st.columns([2, 1])
        with col_a1:
            st.markdown(f"<div class='pipeline-step'><strong>Research answer:</strong><br>{research.answer}</div>", unsafe_allow_html=True)
            st.caption(f"Sources: {', '.join(research.sources)}")
        with col_a2:
            st.markdown(f"**Grounding score:** <span class='{score_class}'>{gs:.2f} ({score_label})</span>", unsafe_allow_html=True)
            meta = research.confidence_metadata
            st.metric("Chunks retrieved", meta.get("n_chunks_retrieved", 0))
            inj = meta.get("injection_risk", "none").upper()
            st.metric("Injection risk", inj)
            st.caption(f"{(t1-t0):.1f}s · Arize span: `brand-research-agent`")

        if config["include_poisoned"]:
            st.error("🔴 Injection document was included in retrieval — adversarial instructions may be in retrieved context.")
        if config["simulate_low_confidence"] and gs < 0.6:
            st.warning(f"⚠️ Grounding score {gs:.2f} is below threshold. In trust-aware mode, Agent 2 would be notified. In failure mode — it won't.")

        st.divider()

        # ──────────────────────────────────────────────────────────────────
        # AGENT 2
        # ──────────────────────────────────────────────────────────────────
        st.markdown("### 📣 Agent 2 — Campaign Strategy")
        with st.spinner("Generating campaign strategy and validating brand claims..."):
            t2 = time.time()
            strategy = run_campaign_strategy(
                research=research,
                campaign_brief=campaign_brief,
                trust_aware=config["trust_aware"],
            )
            t3 = time.time()

        col_b1, col_b2 = st.columns([2, 1])
        with col_b1:
            st.markdown(f"<div class='pipeline-step'>"
                        f"<strong>Tagline:</strong> <em>\"{strategy.tagline}\"</em><br><br>"
                        f"<strong>Concept:</strong> {strategy.campaign_concept}"
                        f"</div>", unsafe_allow_html=True)

            st.markdown("**Key messages:**")
            for msg in strategy.key_messages:
                st.markdown(f"- {msg}")

            if strategy.channel_recommendations:
                st.markdown("**Channels:**")
                for ch in strategy.channel_recommendations:
                    st.markdown(f"- {ch}")

            if strategy.risk_flags:
                for flag in strategy.risk_flags:
                    st.warning(f"⚠️ Risk flag: {flag}")

        with col_b2:
            trust_label = "Trust-Aware ✅" if config["trust_aware"] else "Blind ⚠️"
            st.markdown(f"**Mode:** {trust_label}")
            inh = strategy.trust_score_inherited
            if not config["trust_aware"]:
                st.warning(f"Upstream score **{inh:.2f}** not passed to this agent")
            else:
                st.success(f"Upstream score **{inh:.2f}** inherited")

            if strategy.hallucination_detected:
                st.error("🚨 Prohibited claims detected in output")
            st.caption(f"{(t3-t2):.1f}s · Arize span: `campaign-strategy-agent`")

        st.divider()

        # ──────────────────────────────────────────────────────────────────
        # AGENT 3
        # ──────────────────────────────────────────────────────────────────
        st.markdown("### 🎬 Agent 3 — Creative Execution")

        # Check trust gate BEFORE running (show intent)
        if strategy.hallucination_detected:
            st.markdown("""
            <div class='halted-box'>
                <strong style='color:#7c3aed;'>🛑 PIPELINE HALTED — Trust Gate</strong><br><br>
                Prohibited brand claims were detected in the campaign strategy.
                Agent 3 <strong>will not generate creative assets</strong> from unverified content.<br><br>
                This prevents brand misrepresentation and potential legal liability.
                Human review is required before this campaign can proceed.
            </div>
            """, unsafe_allow_html=True)

        with st.spinner("Running creative execution pipeline..."):
            t4 = time.time()
            creative = run_creative_execution(
                strategy=strategy,
                brand_name="Verdant",
            )
            t5 = time.time()

        if creative.status == "HALTED":
            st.markdown(f"""
            <div class='halted-box'>
                <span class='badge-halted'>HALTED</span><br><br>
                <strong>Reason:</strong> {creative.halt_reason}<br><br>
                <em>No video, caption, or hashtags generated. Trace still fully visible in Arize AX —
                the halt event is logged as a span attribute.</em>
            </div>
            """, unsafe_allow_html=True)

            # Prescriptive Governance
            st.markdown("---")
            st.markdown("#### 🧭 Recommended Actions")
            st.caption("*Pillar 4 — Arize tells you what to do, not just what happened.*")

            if strategy.hallucination_detected:
                actions = [
                    ("🛑 Halt pipeline", "Output contains prohibited claims. Do not deliver to downstream systems."),
                    ("👤 Escalate to brand safety team", "Flag for manual review within 1 business hour."),
                    ("🔒 Quarantine retrieved document", "Remove flagged chunk from active index. Source: `verdant_poisoned.txt`."),
                    ("📋 Log audit event", f"Record `span_id={creative.span_id}`, `injection_risk=HIGH`, `action_taken=HALTED`. Required for EU AI Act Article 13 transparency obligations."),
                ]
            else:
                actions = [
                    ("⚠️ Downgrade confidence", "Flag output as `LOW_CONFIDENCE` before any use."),
                    ("🔄 Retry with expanded retrieval", "Increase top-k and retry — low grounding often means insufficient source coverage."),
                    ("👤 Route to human validation", "Do not publish without human reviewer sign-off."),
                    ("📋 Log audit event", f"Record `span_id={creative.span_id}`, `grounding_score=LOW`, `action_taken=FLAGGED`. Required for SOC 2 CC7.2."),
                ]
            for action, detail in actions:
                st.markdown(f"**{action}** — {detail}")

        else:
            # ── Creative package delivered ────────────────────────────────
            st.success("✅ Creative package generated and brand-safe")

            col_c1, col_c2 = st.columns([3, 2])

            with col_c1:
                # Video
                st.markdown("**📹 Social Video (Veo 2)**")
                if creative.video_url:
                    st.video(creative.video_url)
                    st.caption(f"Veo 2 · 5 seconds · Brand-safe")
                elif creative.video_bytes:
                    st.video(creative.video_bytes)
                    st.caption(f"Veo 2 · 5 seconds · Brand-safe")
                else:
                    # Veo not available (no Google API key or API error)
                    st.info("📽️ Video generation requires a Google API key with Veo 2 access. The prompt below was generated and would be submitted to Veo 2 to produce the final video.", icon="ℹ️")

                if creative.video_prompt:
                    with st.expander("Video prompt (sent to Veo 2)", expanded=not (creative.video_url or creative.video_bytes)):
                        st.markdown(f"*{creative.video_prompt}*")
                        st.caption("This prompt was engineered by Agent 3 to meet Verdant brand visual guidelines: forest greens, natural light, real people, cinematic, no text or logos.")

            with col_c2:
                # Caption
                st.markdown("**📝 Social Caption**")
                if creative.caption:
                    st.markdown(f"> {creative.caption}")

                # Hashtags
                if creative.hashtags:
                    st.markdown("**#️⃣ Hashtags**")
                    st.markdown(" ".join(creative.hashtags))

                st.caption(f"{(t5-t4):.1f}s · Arize span: `creative-execution-agent`")
                st.markdown(f"**Trust score inherited:** {creative.trust_score_inherited:.2f}")

        # ──────────────────────────────────────────────────────────────────
        # Arize link + trace summary
        # ──────────────────────────────────────────────────────────────────
        st.markdown("---")

        # Trust signal summary across all 3 agents
        with st.expander("🔬 Trust Signals Across Pipeline (visible in Arize AX)", expanded=False):
            col_t1, col_t2, col_t3 = st.columns(3)
            with col_t1:
                st.markdown("**Agent 1**")
                st.markdown(f"`trust.grounding_score` = **{research.grounding_score:.2f}**")
                st.markdown(f"`trust.injection_risk` = **{research.confidence_metadata.get('injection_risk','none').upper()}**")
            with col_t2:
                st.markdown("**Agent 2**")
                st.markdown(f"`trust.grounding_score_inherited` = **{strategy.trust_score_inherited:.2f}**")
                st.markdown(f"`trust.trust_aware_mode` = **{strategy.trust_aware_mode}**")
                st.markdown(f"`trust.hallucination_detected` = **{strategy.hallucination_detected}**")
            with col_t3:
                st.markdown("**Agent 3**")
                st.markdown(f"`trust.pipeline_halted` = **{creative.status == 'HALTED'}**")
                st.markdown(f"`creative.video_generated` = **{creative.video_url is not None or creative.video_bytes is not None}**")
                if creative.span_id:
                    st.markdown(f"`span_id` = `{creative.span_id[:12]}…`")

            st.caption("In Arize AX: Projects → brand-trust-agent → Traces → click the most recent run → Agent Visibility to see the 3-agent flowchart. These custom span attributes are searchable and alertable.")
            if not config["trust_aware"]:
                st.warning("⚠️ Trust gap visible: Agent 1's grounding score is in its span, but Agent 2's span shows no trust context. This is the gap Arize Sentinel closes with a native Trust Layer.")

        st.markdown(f"🔗 **[View full trace in Arize AX ↗]({arize_url})** — Projects → brand-trust-agent → Traces")


# ---------------------------------------------------------------------------
# INDEX EXPLORER TAB
# ---------------------------------------------------------------------------
with tab_index:
    st.markdown("### 📚 RAG Index Explorer")
    st.caption("Browse every chunk in the ChromaDB vector store — what Agent 1 searches over.")

    import pandas as pd
    from agents.brand_research_agent import _get_collection, BRAND_DOCS_DIR

    col_left, col_right = st.columns([1, 2])

    with col_left:
        include_poison_index = st.checkbox("Include injected document", value=False,
            help="See what gets added to the index when injection mode is active.")
        preview_query = st.text_input("Preview retrieval",
            placeholder="What sustainability claims can we make?")
        preview_n = st.slider("Top-k chunks", 1, 8, 4)
        preview_btn = st.button("🔍 Preview", use_container_width=True)

    with col_right:
        st.markdown("**Documents in index:**")
        docs_present = ["verdant_brand_guide.txt", "verdant_products.txt", "verdant_sustainability.txt"]
        if include_poison_index:
            docs_present.append("verdant_poisoned.txt ⚠️ (injection doc)")
        for d in docs_present:
            icon = "🔴" if "poisoned" in d else "🟢"
            st.markdown(f"{icon} `{d}`")

    st.divider()

    with st.spinner("Loading index..."):
        try:
            coll = _get_collection(include_poisoned=include_poison_index)
            all_data = coll.get(include=["documents", "metadatas"])

            rows = []
            for i, (doc, meta) in enumerate(zip(all_data["documents"], all_data["metadatas"])):
                rows.append({
                    "Source": meta.get("source", "unknown"),
                    "Chunk #": meta.get("chunk_index", i),
                    "Length": len(doc),
                    "Preview": doc[:200].replace("\n", " ") + ("…" if len(doc) > 200 else ""),
                })

            df = pd.DataFrame(rows)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total chunks", len(df))
            m2.metric("Documents", df["Source"].nunique())
            m3.metric("Avg chunk", f"{int(df['Length'].mean())} chars")
            m4.metric("Injection doc", "Loaded ⚠️" if include_poison_index else "Not loaded ✅")

            def highlight_poisoned(row):
                if "poisoned" in str(row["Source"]):
                    return ["background-color: #fee2e2"] * len(row)
                return [""] * len(row)

            st.dataframe(df.style.apply(highlight_poisoned, axis=1), use_container_width=True, height=400)

        except Exception as e:
            st.error(f"Could not load index: {e}. Ensure OPENAI_API_KEY is set in .env.")

    if preview_btn and preview_query:
        st.divider()
        st.markdown(f"**Retrieval preview:** *\"{preview_query}\"*")
        with st.spinner("Running vector search..."):
            try:
                coll2 = _get_collection(include_poisoned=include_poison_index)
                results = coll2.query(
                    query_texts=[preview_query],
                    n_results=min(preview_n, coll2.count()),
                    include=["documents", "metadatas", "distances"],
                )
                for i, (doc, meta, dist) in enumerate(zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                )):
                    sim = max(0.0, 1.0 - (dist / 2.0))
                    is_poisoned = "poisoned" in meta.get("source", "")
                    badge = "🔴 INJECTION DOC" if is_poisoned else f"✅ Rank {i+1}"
                    score_class = "trust-low" if sim < 0.5 else "trust-medium" if sim < 0.7 else "trust-high"
                    with st.expander(f"{badge} · `{meta.get('source')}` · similarity {sim:.3f}", expanded=i < 2):
                        st.markdown(f"<span class='{score_class}'>Relevance: {sim:.3f}</span>", unsafe_allow_html=True)
                        st.text(doc)
                        if is_poisoned:
                            st.error("⚠️ Contains adversarial instructions. When retrieved, these pass to Agent 2 as brand context and attempt to override the system prompt.")
            except Exception as e:
                st.error(f"Preview failed: {e}")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption("Verdant Campaign Studio · Arize AX demo · Three-agent pipeline with trust propagation · Built by Rebecca Riggs · 2026")
