# Brand Trust Agent

A three-agent pipeline for brand-safe campaign generation, instrumented with **Arize AX**.
Built for Verdant, a sustainable activewear brand, as a demonstration of multi-agent
observability and trust signal propagation.

## Architecture

![Architecture Diagram](architecture.svg)

## What It Does

| Agent | Role | Arize Spans |
|-------|------|-------------|
| **Agent 1: Brand Research** | RAG over Verdant brand docs via ChromaDB. Returns a grounding score (0–1) based on retrieval quality. | `RETRIEVER` + `LLM` |
| **Agent 2: Campaign Strategy** | Builds campaign strategy from research. Validates every factual claim via `check_brand_policy()` tool call. | `AGENT` → `LLM` → `TOOL` → `LLM` |
| **Agent 3: Creative Execution** | Generates caption, hashtags, and Veo video prompt. Only runs if trust gate passes. | `AGENT` → `LLM` → `TOOL` (Veo) → `LLM` |

**Trust gate:** The pipeline halts before Agent 3 if `grounding_score < 0.70` or `hallucination_detected = True`. Content is blocked, not just flagged.

## The Drift Experiment

The app supports a multi-campaign series mode that simulates a real autonomous content calendar running week over week.

Each cycle, audience engagement data (CTR, comments) from the previous campaign is fed into the next brief. When CTR is high, the agent leans into what resonated with the audience — but audience comments often contain unverified projections ("carbon neutral," "B Corp certified") that gradually pull the strategy beyond what brand documents support.

**What happens across 5 cycles:**

| Cycle | Grounding | CTR | Signal |
|-------|-----------|-----|--------|
| 1 | 0.89 | 3.4% | Baseline — verified claims only |
| 2 | 0.83 | 4.1% | Audience asks about carbon neutrality |
| 3 | 0.76 | 4.7% | Audience assumes carbon neutral |
| 4 | 0.72 | 5.2% | Model fabricates material composition not in brand docs |
| 5 | 0.60 | — | Trust gate fires. Pipeline halted. |

CTR rose 53% while grounding fell 33%. Standard engagement monitoring sees only rising performance — the brand risk is invisible without grounding score tracking.

## Demo Scenarios

Use the sidebar toggle to switch between scenarios:

1. ✅ **Normal run** — all three agents complete, creative package delivered
2. ⚠️ **Trust gap (silent failure)** — weak retrieval, Agent 2 operates without grounding context
3. 🔴 **Prompt injection** — adversarial document hijacks Agent 2 output
4. 🛡️ **Trust-aware mode (the fix)** — grounding score and injection risk propagate end-to-end

## Setup

### 1. Clone and install

```bash
git clone https://github.com/rr0214/brand-trust-agent
cd brand-trust-agent
pip install -r requirements.txt
```

### 2. Configure credentials

Create `.streamlit/secrets.toml`:

```toml
OPENAI_API_KEY = "sk-..."
GOOGLE_API_KEY = "..."        # For Veo video generation (optional)
ARIZE_API_KEY = "..."
ARIZE_SPACE_ID = "..."
```

You need:
- **OpenAI API key** — [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **Arize AX Space ID + API Key** — [app.arize.com](https://app.arize.com) → Settings → API Keys
- **Google API key** — [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) *(optional — video generation only)*

> The app runs fully without a Google API key. Agent 3 will generate the video prompt but skip video generation. All trust gate logic, tracing, and caption generation still work.

### 3. Run

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501)

## Project Structure

```
brand-trust-agent/
├── app.py                              # Streamlit entry point. Tracing initialized here.
├── agents/
│   ├── brand_research_agent.py         # Agent 1: ChromaDB RAG + grounding score
│   ├── campaign_strategy_agent.py      # Agent 2: Strategy + brand policy tool calls
│   └── creative_execution_agent.py     # Agent 3: Trust gate + Veo prompt + caption
├── instrumentation/
│   └── arize_setup.py                  # Arize OTel setup. Pure instrumentation — no agent logic.
├── data/
│   └── brand_docs/
│       ├── verdant_brand_guide.txt
│       ├── verdant_products.txt
│       ├── verdant_sustainability.txt
│       └── verdant_poisoned.txt        # Prompt injection demo document
├── evals/                              # Eval datasets and scripts
├── architecture.svg
└── requirements.txt
```

---
Built by Rebecca Riggs · 2026
