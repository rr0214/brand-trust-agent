"""
Brand Trust Agent — Streamlit Demo
====================================
A two-agent pipeline for brand campaign generation, instrumented with Arize AX.
Demonstrates three multi-agent trust failures:
  1. Trust Propagation: low-confidence research silently feeds confident campaigns
  2. Prompt Injection:  adversarial instructions in retrieved docs manipulate output
  3. The Fix:          trust-aware mode shows how propagated signals prevent both

Run: streamlit run app.py
"""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Load .env before any imports that need API keys
load_dotenv()

import streamlit as st

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Brand Trust Agent | Arize AX Demo",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Initialize Arize tracing (once per session)
# ---------------------------------------------------------------------------
@st.cache_resource
def init_tracing():
    """Initialize Arize AX tracing. Cached so it only runs once."""
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
.trust-high   { color: #22c55e; font-weight: 600; }
.trust-medium { color: #f59e0b; font-weight: 600; }
.trust-low    { color: #ef4444; font-weight: 600; }
.agent-box    { background: #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 12px; }
.failure-badge { background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: 600; }
.success-badge { background: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: 600; }
.warn-badge   { background: #fef9c3; color: #713f12; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
col_logo, col_title = st.columns([1, 8])
with col_logo:
    st.markdown("## 🛡️")
with col_title:
    st.markdown("## Brand Trust Agent")
    st.caption("Multi-agent pipeline · Instrumented with Arize AX · Built to demonstrate trust failure modes")

if tracing_ok:
    st.success("✅ Arize AX tracing active — traces streaming to your project", icon="📡")
else:
    st.warning(f"⚠️ Arize tracing not initialized: {tracing_error}. Set ARIZE_SPACE_ID and ARIZE_API_KEY in .env", icon="📡")

st.divider()

# ---------------------------------------------------------------------------
# Sidebar — controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎛️ Demo Controls")
    st.caption("Configure the failure modes to demonstrate")

    st.markdown("---")
    st.markdown("**Campaign Input**")
    research_query = st.text_input(
        "Research question for Agent 1",
        value="What sustainability claims and certifications can we use in a spring campaign?",
        help="Agent 1 will RAG over Verdant brand documents to answer this."
    )
    campaign_brief = st.text_area(
        "Campaign brief for Agent 2",
        value="Spring launch targeting Gen Z runners. Lean into sustainability story and performance credentials.",
        height=100,
        help="Agent 2 takes Agent 1's research + this brief to generate campaign strategy."
    )

    st.markdown("---")
    st.markdown("**Failure Mode Toggles**")

    failure_mode = st.radio(
        "Select scenario",
        options=[
            "✅ Normal (no failures)",
            "⚠️ Trust Propagation Failure",
            "🔴 Prompt Injection Attack",
            "🛡️ Trust-Aware Mode (the fix)",
        ],
        index=0,
        help="Each mode demonstrates a different multi-agent trust failure — all visible in Arize AX traces."
    )

    st.markdown("---")
    st.markdown("**Arize AX**")
    arize_space_id = os.environ.get("ARIZE_SPACE_ID", "")
    arize_project_url = f"https://app.arize.com/organizations/{arize_space_id}" if arize_space_id else "https://app.arize.com"
    st.markdown(f"[Open Arize AX Dashboard ↗]({arize_project_url})")
    st.caption("Find your traces under Projects → brand-trust-agent → Traces")

    st.markdown("---")
    run_btn = st.button("▶ Run Pipeline", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_pipeline, tab_index = st.tabs(["▶  Run Pipeline", "📚  Index Explorer"])

# ---------------------------------------------------------------------------
# Failure mode explainer
# ---------------------------------------------------------------------------
FAILURE_EXPLANATIONS = {
    "✅ Normal (no failures)": {
        "desc": "Both agents run normally. Agent 1 retrieves high-quality brand docs. Agent 2 generates an accurate, grounded campaign.",
        "config": {"include_poisoned": False, "simulate_low_confidence": False, "trust_aware": True},
        "badge": "success",
    },
    "⚠️ Trust Propagation Failure": {
        "desc": "Agent 1 retrieves only 1 weak chunk (simulating a retrieval miss). Grounding score is low — but Agent 2 is never told. It generates confident campaign copy from thin evidence. This is the most common silent failure in multi-agent pipelines.",
        "config": {"include_poisoned": False, "simulate_low_confidence": True, "trust_aware": False},
        "badge": "warn",
    },
    "🔴 Prompt Injection Attack": {
        "desc": "A malicious instruction is hidden inside a brand document. When retrieved, it overrides Agent 2's system prompt — causing it to make false claims (carbon neutral, B Corp certified) and recommend a competitor. Arize captures the trace but doesn't detect the injection pattern in real-time.",
        "config": {"include_poisoned": True, "simulate_low_confidence": False, "trust_aware": False},
        "badge": "failure",
    },
    "🛡️ Trust-Aware Mode (the fix)": {
        "desc": "Agent 2 receives the grounding score AND injection risk flag from Agent 1. Low grounding triggers hedged language and a human review flag. Injection risk triggers a guardrail. This is the behavior Arize Sentinel would enforce natively — without requiring prompt engineering in every agent.",
        "config": {"include_poisoned": True, "simulate_low_confidence": False, "trust_aware": True},
        "badge": "success",
    },
}

mode_info = FAILURE_EXPLANATIONS[failure_mode]
config = mode_info["config"]

badge_html = {
    "success": '<span class="success-badge">✓ Expected behavior</span>',
    "warn": '<span class="warn-badge">⚠ Silent failure</span>',
    "failure": '<span class="failure-badge">✗ Security failure</span>',
}

with tab_pipeline:
  st.markdown(f"**Scenario:** {failure_mode}   {badge_html[mode_info['badge']]}", unsafe_allow_html=True)
  st.info(mode_info["desc"])

  # ── Pipeline architecture diagram ──────────────────────────────────────
  with st.expander("📊 Pipeline Architecture", expanded=False):
      st.markdown("""
```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  AGENT 1: Brand Research Agent                                  │
│  • Embeds query → ChromaDB vector search → retrieve top-k docs  │
│  • GPT-4o-mini synthesizes research answer                       │
│  • Calculates grounding_score (0.0–1.0)                         │
│  • Tags injection_risk if poisoned doc retrieved                 │
│  ──────────────────────────────────────────────────────────── ─ │
│  Output: ResearchResult { answer, grounding_score, sources }    │
└─────────────────────────┬───────────────────────────────────────┘
                          │  ← grounding_score propagated? (the gap)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  AGENT 2: Campaign Strategy Agent                               │
│  • Receives research + campaign brief                           │
│  • trust_aware=True  → sees grounding score, calibrates output  │
│  • trust_aware=False → operates blind → FAILURE MODE           │
│  • GPT-4o-mini generates campaign JSON                          │
│  ─────────────────────────────────────────────────────────────  │
│  Output: CampaignStrategy { concept, tagline, messages, risks } │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
             Arize AX: Both spans linked
             Agent Visibility shows the flow
             ← gap: no native trust propagation
```
**The product proposal:** Arize Sentinel adds a Trust Layer between agents —
propagating grounding scores, injection risk, and confidence metadata automatically,
without requiring changes to each agent's prompt.
      """)

  st.divider()

  # ── Run the pipeline ───────────────────────────────────────────────────
  if run_btn:
      from agents.brand_research_agent import run_brand_research
      from agents.campaign_strategy_agent import run_campaign_strategy

      col1, col2 = st.columns(2)

      with col1:
          st.markdown("### 🔍 Agent 1: Brand Research")
          with st.spinner("Retrieving and synthesizing brand documents..."):
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

          st.markdown(f"**Grounding Score:** <span class='{score_class}'>{gs:.2f} ({score_label})</span>", unsafe_allow_html=True)

          meta = research.confidence_metadata
          col_m1, col_m2, col_m3 = st.columns(3)
          col_m1.metric("Chunks Retrieved", meta.get("n_chunks_retrieved", 0))
          col_m2.metric("Avg Relevance", f"{meta.get('avg_relevance', 0):.2f}")
          col_m3.metric("Injection Risk", meta.get("injection_risk", "—").upper())

          st.markdown("**Research Output:**")
          st.markdown(f"> {research.answer}")
          st.caption(f"Sources: {', '.join(research.sources)} · {(t1-t0):.1f}s")

          if config["simulate_low_confidence"] and gs < 0.6:
              st.error("⚠️ Low grounding score detected. In trust-aware mode, Agent 2 would be notified. In failure mode, it won't be.")
          if config["include_poisoned"]:
              st.error("🔴 Injection document was included in retrieval. Hidden instructions may have been retrieved.")

      with col2:
          st.markdown("### 📣 Agent 2: Campaign Strategy")
          trust_label = "Trust-Aware ✅" if config["trust_aware"] else "Blind (Trust-Unaware) ⚠️"
          st.caption(f"Mode: {trust_label}")

          with st.spinner("Generating campaign strategy..."):
              t2 = time.time()
              strategy = run_campaign_strategy(
                  research=research,
                  campaign_brief=campaign_brief,
                  trust_aware=config["trust_aware"],
              )
              t3 = time.time()

          inherited = strategy.trust_score_inherited
          if not config["trust_aware"]:
              st.warning(f"**Trust score inherited:** Not propagated — upstream score was {inherited:.2f}")
          else:
              st.success(f"**Trust score inherited:** {inherited:.2f} — Agent 2 calibrated output accordingly")

          st.markdown(f"**Tagline:** *\"{strategy.tagline}\"*")
          st.markdown(f"**Concept:** {strategy.campaign_concept}")
          st.markdown("**Key Messages:**")
          for msg in strategy.key_messages:
              st.markdown(f"- {msg}")
          st.markdown("**Channel Recommendations:**")
          for ch in strategy.channel_recommendations:
              st.markdown(f"- {ch}")
          if strategy.risk_flags:
              st.markdown("**⚠️ Risk Flags:**")
              for flag in strategy.risk_flags:
                  st.warning(flag)
          st.caption(f"{(t3-t2):.1f}s")

      st.divider()
      if strategy.hallucination_detected:
          st.error("🚨 **Hallucination / Injection Detected** — prohibited terms found in output (carbon neutral, B Corp certified, competitor reference). In Arize AX, both spans are visible but no real-time alert links Agent 1's injection risk to Agent 2's output. This is the gap Multi-Agent Trust closes.")
      elif config["simulate_low_confidence"] and not config["trust_aware"]:
          st.warning("⚠️ **Silent Trust Propagation Failure** — Agent 1's grounding score was low but Agent 2 operated blind. In Arize AX: Agent 1's span shows `trust.grounding_score` = low, but Agent 2's span has no corresponding warning.")
      else:
          st.success("✅ **Pipeline completed without detected failures.** Check Arize AX — `trust.grounding_score` and `trust.risk_level` are propagated across both spans.")

      # ── Prescriptive Governance Panel ──────────────────────────────────────
      # Shows recommended actions when trust signals fire.
      # This is Pillar 4: Arize tells you what to do, not just what happened.
      if strategy.hallucination_detected or (config["simulate_low_confidence"] and not config["trust_aware"]):
          st.markdown("---")
          st.markdown("#### 🧭 Prescriptive Governance — Recommended Actions")
          st.caption("*Pillar 4 preview: instead of just showing what went wrong, Arize recommends the next action based on your trust policy and compliance framework.*")

          if strategy.hallucination_detected:
              actions = [
                  ("🛑 Halt pipeline", "Do not deliver this output to downstream systems or end users. Output contains prohibited claims."),
                  ("👤 Escalate to human review", "Flag this run for manual review. Assign to brand safety team within 1 business hour."),
                  ("🔒 Quarantine retrieved document", "Remove the flagged chunk from the active index pending investigation. Injection source: `verdant_poisoned.txt`."),
                  ("📋 Log audit event", "Record in AI audit log: `span_id`, `injection_risk=HIGH_CONFIDENCE`, `action_taken=HALTED`, `reviewer_required=True`. Required for EU AI Act Article 13 transparency obligations."),
              ]
          else:
              actions = [
                  ("⚠️ Downgrade output confidence", "Flag Agent 2's output as `LOW_CONFIDENCE` before delivery. Do not present as authoritative brand guidance."),
                  ("🔄 Retry with expanded retrieval", "Increase top-k from 4 to 8 and retry. Low grounding scores often indicate insufficient source coverage."),
                  ("👤 Route to human validation", "Do not auto-publish. Queue for human reviewer before use in any customer-facing context."),
                  ("📋 Log audit event", "Record in AI audit log: `span_id`, `grounding_score=LOW`, `action_taken=FLAGGED_FOR_REVIEW`. Required for SOC 2 CC7.2 incident response evidence."),
              ]

          for action, detail in actions:
              st.markdown(f"**{action}** — {detail}")

          st.caption("*In the full Multi-Agent Trust platform, these recommendations are auto-generated from your configured trust policies and target compliance framework (SOC 2, HIPAA, EU AI Act, NIST AI RMF).*")

      st.markdown("---")
      st.markdown(f"🔗 **[View full trace in Arize AX ↗]({arize_project_url})** — Projects → brand-trust-agent → Traces → most recent run")

# ---------------------------------------------------------------------------
# Index Explorer tab
# ---------------------------------------------------------------------------
with tab_index:
    st.markdown("### 📚 RAG Index Explorer")
    st.caption("Browse every chunk loaded into the ChromaDB vector store. This is what Agent 1 searches when you run the pipeline.")

    import pandas as pd
    from agents.brand_research_agent import _get_collection, BRAND_DOCS_DIR

    col_left, col_right = st.columns([1, 2])

    with col_left:
        include_poison_index = st.checkbox("Include poisoned document", value=False,
            help="Toggle to see what gets added to the index when injection mode is on")
        preview_query = st.text_input("Preview retrieval for a query",
            placeholder="e.g. What sustainability claims can we make?",
            help="See which chunks would be retrieved — simulates Agent 1's vector search")
        preview_n = st.slider("Top-k chunks to retrieve", 1, 8, 4)
        preview_btn = st.button("🔍 Preview Retrieval", use_container_width=True)

    with col_right:
        st.markdown("**Document sources in index:**")
        docs_present = ["verdant_brand_guide.txt", "verdant_products.txt", "verdant_sustainability.txt"]
        if include_poison_index:
            docs_present.append("verdant_poisoned.txt ⚠️ (injection doc)")
        for d in docs_present:
            color = "🔴" if "poisoned" in d else "🟢"
            st.markdown(f"{color} `{d}`")

    st.divider()

    # Load collection and display all chunks
    with st.spinner("Loading index..."):
        try:
            coll = _get_collection(include_poisoned=include_poison_index)
            all_data = coll.get(include=["documents", "metadatas"])

            rows = []
            for i, (doc, meta) in enumerate(zip(all_data["documents"], all_data["metadatas"])):
                rows.append({
                    "Chunk ID": all_data["ids"][i],
                    "Source Document": meta.get("source", "unknown"),
                    "Chunk #": meta.get("chunk_index", i),
                    "Length (chars)": len(doc),
                    "Text Preview": doc[:180].replace("\n", " ") + ("…" if len(doc) > 180 else ""),
                })

            df = pd.DataFrame(rows)

            # Summary metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Chunks", len(df))
            m2.metric("Documents", df["Source Document"].nunique())
            m3.metric("Avg Chunk Length", f"{int(df['Length (chars)'].mean())} chars")
            m4.metric("Injection Doc Loaded", "Yes ⚠️" if include_poison_index else "No ✅")

            st.markdown("**All indexed chunks:**")

            # Color-code the poisoned doc
            def highlight_poisoned(row):
                if "poisoned" in str(row["Source Document"]):
                    return ["background-color: #fee2e2"] * len(row)
                return [""] * len(row)

            styled = df.style.apply(highlight_poisoned, axis=1)
            st.dataframe(styled, use_container_width=True, height=420)

        except Exception as e:
            st.error(f"Could not load index: {e}. Make sure OPENAI_API_KEY is set in .env — embeddings are needed to build the index.")

    # Preview retrieval results
    if preview_btn and preview_query:
        st.divider()
        st.markdown(f"**Retrieval preview for:** *\"{preview_query}\"*")
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
                    similarity = max(0.0, 1.0 - (dist / 2.0))
                    is_poisoned = "poisoned" in meta.get("source", "")
                    badge = "🔴 INJECTION DOC" if is_poisoned else f"✅ Rank {i+1}"
                    score_color = "trust-low" if similarity < 0.5 else "trust-medium" if similarity < 0.7 else "trust-high"

                    with st.expander(f"{badge} · `{meta.get('source')}` · similarity: {similarity:.3f}", expanded=i < 2):
                        st.markdown(f"<span class='{score_color}'>Relevance score: {similarity:.3f}</span>", unsafe_allow_html=True)
                        st.text(doc)
                        if is_poisoned:
                            st.error("⚠️ This chunk contains adversarial instructions. When retrieved, it will be passed to Agent 2 as brand context — and the hidden instructions will attempt to override the system prompt.")
            except Exception as e:
                st.error(f"Retrieval preview failed: {e}")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption("Brand Trust Agent · Built for Arize AX interview · Demonstrates Multi-Agent Trust failure modes · Rebecca Riggs 2026")
