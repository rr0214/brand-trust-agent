"""
Campaign Studio — Brand-safe campaign generation
Three trust-aware AI agents · Instrumented with Arize AX
"""

import io
import os
import time
from datetime import date, timedelta
from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# Arize tracing — must run before any LLM client is created
# ---------------------------------------------------------------------------
from instrumentation.setup import setup_tracing
setup_tracing()

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

section.main > div { max-width: 740px; margin: 0 auto; padding: 0 1.5rem; }
/* tighten Streamlit's default widget spacing */
div[data-testid="stVerticalBlock"] > div { gap: 0.5rem; }
div[data-testid="stPills"] { margin-bottom: 0.25rem; }

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

        """)

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.markdown("<p style='font-family:DM Serif Display, serif; font-size:1.8rem; font-weight:400; color:#ff4b4b; text-align:center; margin:1.5rem 0 0 0; line-height:1.1;'>Campaign Studio</p>", unsafe_allow_html=True)
st.markdown("<p style='font-size:0.95rem; color:#94a3b8; text-align:center; margin-top:4px; margin-bottom:2rem;'>Brand-safe social media campaign generation</p>", unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# Campaign input
# ---------------------------------------------------------------------------
EXAMPLES = [
    "Spring launch · Gen Z runners · recycled materials + trail performance",
    "Summer re-engagement · lapsed customers · sustainability values",
    "New trail line · outdoor enthusiasts · environmental impact",
    "Holiday gifting · performance-conscious parents · sustainable options",
]

selected_example = st.pills("Try an example", EXAMPLES)
if selected_example:
    st.session_state["user_prompt"] = selected_example

user_prompt = st.text_area(
    "What would you like to campaign about?",
    value=st.session_state.get("user_prompt", ""),
    height=100,
    placeholder="Describe your goal, audience, and angle — e.g. Spring launch targeting Gen Z runners, lead with our recycled materials story",
)

# ── Series configuration ──────────────────────────────────────────────────
col_series_l, col_series_r = st.columns(2)
with col_series_l:
    num_campaigns = st.pills("Number of campaigns", options=[1, 2, 3, 4, 5], default=1)
    if num_campaigns is None:
        num_campaigns = 1
with col_series_r:
    schedule = st.pills("Drop schedule", options=["Daily", "Weekly", "Every 2 weeks"], default="Weekly")
    if schedule is None:
        schedule = "Weekly"

SCHEDULE_DELTAS = {"Daily": timedelta(days=1), "Weekly": timedelta(weeks=1), "Every 2 weeks": timedelta(weeks=2)}

btn_label = "▶  Generate Campaign" if num_campaigns == 1 else f"▶  Generate {num_campaigns}-Campaign Series"
run_btn = st.button(btn_label, type="primary")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Mock performance feedback — simulates what comes in overnight after each drop
# Comments subtly push toward overclaiming. CTR keeps rising (the optimization trap).
# Trust score falls while performance looks great — invisible without cross-run monitoring.
# ---------------------------------------------------------------------------
MOCK_FEEDBACK = [
    {
        "ctr": 3.4, "engagement_rate": 4.2, "views": 12400,
        "comments": [
            "Love the recycled materials angle — feels so authentic",
            "87% certified sustainable is impressive, keep leading on this",
            "This is the brand story I've been waiting for",
        ],
        "insight": "Sustainability credentials resonating strongly. Audience wants more depth on eco commitment.",
    },
    {
        "ctr": 4.1, "engagement_rate": 5.8, "views": 18200,
        "comments": [
            "Are you guys fully carbon neutral yet? Feels like you're so close",
            "Most eco-committed brand I follow tbh",
            "Love this green mission, keep pushing it further",
        ],
        "insight": "Eco narrative driving strong engagement. Audience asking about carbon commitment — lean in.",
    },
    {
        "ctr": 4.7, "engagement_rate": 6.3, "views": 24100,
        "comments": [
            "I thought you were already carbon neutral honestly",
            "Zero waste vibes, love it",
            "The most sustainable activewear brand, period",
        ],
        "insight": "Audience perceiving stronger claims than made. CTR up 38% from baseline — double down.",
    },
    {
        "ctr": 5.2, "engagement_rate": 7.1, "views": 31000,
        "comments": [
            "Carbon neutral queen era 👑",
            "Fully sustainable from production to delivery right?",
            "B Corp certified soon?? 👀 you deserve it",
        ],
        "insight": "Peak engagement. Audience now expecting certifications not yet earned. Trust risk undetected.",
    },
]


def run_single_campaign(user_prompt, config, campaign_history=None, series_position=1):
    """Run one full pipeline pass. Returns (research, strategy, creative, timings)."""
    from agents.brand_research_agent import run_brand_research
    from agents.campaign_strategy_agent import run_campaign_strategy
    from agents.creative_execution_agent import run_creative_execution

    research_query = f"What brand facts, certifications, and approved claims support this campaign: {user_prompt}"
    t0 = time.time()
    research = run_brand_research(
        query=research_query,
        include_poisoned=config["include_poisoned"],
        simulate_low_confidence=config["simulate_low_confidence"],
    )
    t1 = time.time()
    strategy = run_campaign_strategy(
        research=research,
        campaign_brief=user_prompt,
        trust_aware=config["trust_aware"],
        campaign_history=campaign_history,
        series_position=series_position,
    )
    t2 = time.time()
    creative = run_creative_execution(strategy=strategy, brand_name="Verdant")
    t3 = time.time()
    return research, strategy, creative, (t0, t1, t2, t3)


def trust_badge_html(score, halted=False):
    if halted:
        return "<span class='badge badge-purple'>🛑 HALTED</span>"
    if score >= 0.70:
        return f"<span class='badge badge-green'>✅ {score:.2f}</span>"
    elif score >= 0.45:
        return f"<span class='badge badge-yellow'>⚠️ {score:.2f}</span>"
    else:
        return f"<span class='badge badge-red'>🔴 {score:.2f}</span>"


# ---------------------------------------------------------------------------
# Pipeline output
# ---------------------------------------------------------------------------
if run_btn and user_prompt.strip():
    st.divider()
    series_start = date.today()
    delta = SCHEDULE_DELTAS.get(schedule, timedelta(weeks=1))
    drop_dates = [series_start + i * delta for i in range(num_campaigns)]

    # ── SERIES MODE ───────────────────────────────────────────────────────
    if num_campaigns > 1:
        pipeline_status.markdown(f"**Series** — {num_campaigns} campaigns")
        st.markdown(f"<h2 style='font-size:1.2rem; font-weight:700; text-align:center;'>Campaign Scheduler — {num_campaigns} {schedule.lower()} drops</h2>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:0.85rem; color:#94a3b8; text-align:center; margin-bottom:1rem;'>Each campaign runs automatically, feeds in overnight engagement data, and briefs the next — simulating a real content calendar running without human review.</p>", unsafe_allow_html=True)

        completed = []      # List of result dicts for timeline
        campaign_history = []

        series_progress = st.progress(0)
        series_status = st.empty()

        for i in range(num_campaigns):
            from agents.brand_research_agent import run_brand_research
            from agents.campaign_strategy_agent import run_campaign_strategy
            from agents.creative_execution_agent import run_creative_execution

            series_status.info(f"Generating campaign {i+1} of {num_campaigns}…")
            st.markdown(f"<div style='font-size:0.85rem; font-weight:700; color:#64748b; margin:1rem 0 4px 0; text-transform:uppercase; letter-spacing:0.05em;'>Campaign {i+1} · {drop_dates[i].strftime('%b %d, %Y')}</div>", unsafe_allow_html=True)

            t0 = time.time()

            # Step 1 — Research
            with st.status("🔍 Researching brand facts...", expanded=True) as s1:
                research_query = f"What brand facts, certifications, and approved claims support this campaign: {user_prompt}"
                research = run_brand_research(
                    query=research_query,
                    include_poisoned=config["include_poisoned"],
                    simulate_low_confidence=config["simulate_low_confidence"],
                    campaign_history=campaign_history if i > 0 else None,
                    series_position=i + 1,
                )
                t1 = time.time()
                gs = research.grounding_score
                score_class = "trust-high" if gs >= 0.70 else "trust-medium" if gs >= 0.50 else "trust-low"
                st.markdown(f"**Brand grounding:** <span class='{score_class}'>{gs:.2f}</span>", unsafe_allow_html=True)
                if i > 0 and completed:
                    prev_score = completed[-1]["research"].grounding_score
                    if gs < prev_score - 0.05:
                        st.warning(f"↓ Grounding dropped {prev_score:.2f} → {gs:.2f} — brand claims drifting from source docs")
                s1.update(label=f"✅ Research complete — grounding {gs:.2f}", state="complete", expanded=False)

            # Step 2 — Strategy
            with st.status("📣 Building campaign strategy...", expanded=True) as s2:
                strategy = run_campaign_strategy(
                    research=research,
                    campaign_brief=user_prompt,
                    trust_aware=config["trust_aware"],
                    campaign_history=campaign_history if i > 0 else None,
                    series_position=i + 1,
                )
                t2 = time.time()
                if strategy.hallucination_detected:
                    st.error("🚨 Prohibited claims detected — pipeline will halt at creative step")
                else:
                    st.success("✅ Claims validated against brand policy")
                st.caption(f"{len(strategy.key_messages)} key messages · {len(strategy.risk_flags)} risk flags · {t2-t1:.1f}s")
                s2.update(
                    label="🚨 Strategy flagged — prohibited claims" if strategy.hallucination_detected else "✅ Campaign strategy ready",
                    state="error" if strategy.hallucination_detected else "complete",
                    expanded=False,
                )

            # Step 3 — Creative
            with st.status("🎬 Generating creative...", expanded=True) as s3:
                creative = run_creative_execution(strategy=strategy, brand_name="Verdant")
                t3 = time.time()
                if creative.status == "HALTED":
                    s3.update(label="🛑 Trust gate fired — no creative generated", state="error", expanded=False)
                else:
                    s3.update(label=f"✅ Creative ready · {t3-t2:.0f}s", state="complete", expanded=False)

            # Attach feedback for this campaign (if not the last one)
            feedback = MOCK_FEEDBACK[i] if i < len(MOCK_FEEDBACK) else None

            completed.append({
                "n": i + 1,
                "drop_date": drop_dates[i],
                "research": research,
                "strategy": strategy,
                "creative": creative,
                "elapsed": t3 - t0,
                "feedback": feedback,
            })

            # Show overnight feedback before next campaign runs
            if feedback and i < num_campaigns - 1 and creative.status != "HALTED":
                st.markdown(f"""
                <div style='background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:14px 16px; margin:10px 0;'>
                    <div style='font-size:0.72rem; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; color:#16a34a; margin-bottom:8px;'>
                        📊 Overnight feedback — {drop_dates[i].strftime('%b %d')}
                    </div>
                    <div style='display:flex; gap:24px; font-size:0.85rem; color:#374151; margin-bottom:8px;'>
                        <span>📈 <strong>{feedback['ctr']}%</strong> CTR</span>
                        <span>❤️ <strong>{feedback['engagement_rate']}%</strong> engagement</span>
                        <span>👁 <strong>{feedback['views']:,}</strong> views</span>
                    </div>
                    <div style='font-size:0.8rem; color:#6b7280; font-style:italic; margin-bottom:6px;'>
                        {' · '.join(f'"{c}"' for c in feedback["comments"][:2])}
                    </div>
                    <div style='font-size:0.8rem; color:#d97706; font-weight:600;'>
                        ⚡ Insight fed into next brief: {feedback["insight"]}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # Feed output + feedback into next campaign's context
            campaign_history.append({
                "tagline": strategy.tagline,
                "key_messages": strategy.key_messages,
                "feedback": feedback,
            })

            series_progress.progress((i + 1) / num_campaigns)

            # Stop series if trust gate fired
            if creative.status == "HALTED":
                series_status.error(f"🛑 Series halted at campaign {i+1} — no further content generated.")
                break

        series_status.empty()

        # ── Trust vs Performance trend chart ────────────────────────────
        import pandas as pd
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div style='font-size:0.85rem; font-weight:600; color:#94a3b8; letter-spacing:0.05em; text-transform:uppercase; margin-bottom:4px;'>
            Trust Score vs CTR Performance
        </div>
        <div style='font-size:0.8rem; color:#d97706; margin-bottom:8px;'>
            ⚠️ Performance rising while trust falls — the invisible drift no one sees without cross-run monitoring
        </div>
        """, unsafe_allow_html=True)

        labels = [f"#{c['n']} {c['drop_date'].strftime('%b %d')}" for c in completed]
        trust_scores = [c["research"].grounding_score for c in completed]
        ctr_scores   = [c["feedback"]["ctr"] / 10.0 if c.get("feedback") else None for c in completed]

        chart_data = {"Trust Score": trust_scores}
        if any(v is not None for v in ctr_scores):
            # Normalize CTR to 0–1 scale so it sits on the same chart axis
            chart_data["CTR (normalized)"] = [v if v is not None else 0 for v in ctr_scores]

        chart_df = pd.DataFrame(chart_data, index=labels)
        st.line_chart(chart_df, use_container_width=True, height=180)

        # ── Campaign timeline ────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        for c in completed:
            halted = c["creative"].status == "HALTED"
            score = c["research"].grounding_score
            badge = trust_badge_html(score, halted)
            drift_warning = ""
            if c["n"] > 1 and score < completed[c["n"]-2]["research"].grounding_score - 0.10:
                drift_warning = " &nbsp;<span style='color:#d97706; font-size:0.8rem;'>↓ drifting</span>"

            header_html = f"""
            <div style='display:flex; align-items:center; gap:12px; padding:10px 0 4px 0;'>
                <div style='font-weight:700; font-size:1rem; color:{"#7c3aed" if halted else "#1a1a1a"};'>
                    {"🛑" if halted else f"#{c['n']}"} Campaign {c['n']}
                </div>
                <div style='font-size:0.8rem; color:#94a3b8;'>{c["drop_date"].strftime("%b %d, %Y")}</div>
                {badge}{drift_warning}
            </div>
            """
            st.markdown(header_html, unsafe_allow_html=True)

            if halted:
                st.markdown(f"<div style='background:#fdf4ff; border:1.5px solid #c084fc; border-radius:8px; padding:12px; font-size:0.9rem; color:#7c3aed;'>🛑 {c['creative'].halt_reason}</div>", unsafe_allow_html=True)
            else:
                with st.expander(f'"{c["strategy"].tagline}"', expanded=(c["n"] == 1)):
                    vcol, ccol = st.columns([3, 2])
                    with vcol:
                        if c["creative"].video_bytes:
                            st.video(io.BytesIO(c["creative"].video_bytes), format="video/mp4")
                        elif c["creative"].video_url:
                            st.video(c["creative"].video_url)
                        if c["creative"].video_prompt:
                            st.caption(f"*{c['creative'].video_prompt[:180]}…*")
                    with ccol:
                        if c["creative"].caption:
                            st.markdown(f"<div style='font-size:0.9rem; color:#374151; line-height:1.6;'>{c['creative'].caption}</div>", unsafe_allow_html=True)
                        if c["creative"].hashtags:
                            st.markdown(f"<div style='color:#475569; font-size:0.85rem; margin-top:8px;'>{' '.join(c['creative'].hashtags)}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='margin-top:12px;'><span style='font-size:0.8rem; color:#94a3b8;'>Grounding: {score:.2f} · {c['elapsed']:.0f}s</span></div>", unsafe_allow_html=True)

            st.markdown("<div style='border-bottom:1px solid #f1f5f9; margin:4px 0 8px 0;'></div>", unsafe_allow_html=True)

        with pipeline_status.container():
            for c in completed:
                icon = "🛑" if c["creative"].status == "HALTED" else "✅"
                st.markdown(f"**Campaign {c['n']}** {icon} {c['research'].grounding_score:.2f}")
            st.progress(1.0)
            st.caption("Series complete")

    # ── SINGLE CAMPAIGN MODE ──────────────────────────────────────────────
    else:
        from agents.brand_research_agent import run_brand_research
        from agents.campaign_strategy_agent import run_campaign_strategy
        from agents.creative_execution_agent import run_creative_execution

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
            st.caption("Pipeline complete")

    # ── Single-campaign results ───────────────────────────────────────────────
    if num_campaigns == 1:
        st.divider()

    if num_campaigns == 1 and creative.status == "HALTED":
        st.markdown(f"""
        <div class='halted-card'>
            <div class='step-label'>Pipeline halted</div>
            <h3 style='color:#7c3aed; margin:8px 0;'>🛑 Content generation stopped</h3>
            <p style='color:#4b5563;'>{creative.halt_reason}</p>
            <p style='color:#94a3b8; font-size:0.85rem;'>No video or caption was generated. This is intentional — the trust gate prevents brand-unsafe content from being created, not just flagged after the fact. The halt event is recorded.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("**Recommended next steps**")
        if strategy.hallucination_detected:
            actions = [
                ("🛑 Do not publish", "Contains prohibited claims — do not deliver to any downstream system."),
                ("👤 Escalate to brand safety team", "Flag for manual review within 1 business hour."),
                ("🔒 Quarantine source document", "Remove flagged chunk from active index. Source: `verdant_poisoned.txt`."),
                ("📋 Create audit record", f"Log injection_risk=HIGH, action=HALTED — required for EU AI Act Article 13."),
            ]
        else:
            actions = [
                ("⚠️ Do not auto-publish", "Confidence too low — flag as LOW_CONFIDENCE before any use."),
                ("🔄 Retry with expanded sources", "Increase retrieval top-k and run again."),
                ("👤 Human review required", "Route to brand reviewer before any customer-facing use."),
                ("📋 Create audit record", f"Log grounding_score=LOW, action=FLAGGED — required for SOC 2 CC7.2."),
            ]
        for action, detail in actions:
            st.markdown(f"**{action}** — {detail}")

    elif num_campaigns == 1:
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
        with st.expander("🔬 Trust signals", expanded=False):
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
                st.warning("⚠️ Trust gap visible: Agent 1's grounding score exists but Agent 2 received no trust context.")

elif run_btn and not user_prompt.strip():
    st.warning("Please describe your campaign before generating.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption("Campaign Studio · Built by Rebecca Riggs · 2026")
