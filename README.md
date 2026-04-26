# Brand Trust Agent

A two-agent pipeline for brand campaign generation, instrumented with **Arize AX**.
Built to demonstrate multi-agent trust failure modes and a four-pillar product proposal for the Arize AI observability platform.

## Architecture

![Architecture Diagram](architecture.svg)

## What It Does

| Agent | Role | Failure mode demonstrated |
|-------|------|--------------------------|
| **Agent 1: Brand Research** | RAG over brand docs → grounding score | Low-confidence retrieval, prompt injection |
| **Agent 2: Campaign Strategy** | Generates campaign from research | Blind trust propagation, hallucinated claims |

**Three scenarios you can run from the Streamlit UI:**

1. ✅ **Normal** — both agents run correctly, accurate campaign generated
2. ⚠️ **Trust Propagation Failure** — Agent 1 retrieves weak evidence, Agent 2 doesn't know, makes up claims
3. 🔴 **Prompt Injection** — adversarial instructions hidden in a brand doc hijack Agent 2's output
4. 🛡️ **Trust-Aware Mode** — the fix: grounding score + injection risk propagate between agents

All runs are traced in **Arize AX** → Projects → `brand-trust-agent` → Traces.

## Setup

### 1. Clone and install

```bash
git clone <your-repo>
cd brand-trust-agent
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your API keys
```

You need:
- **OpenAI API key** — [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **Arize AX Space ID + API Key** — [app.arize.com](https://app.arize.com) → Settings → API Keys

### 3. Run the Streamlit app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501)

### 4. Run evaluations (dev workflow)

```bash
# Run 5 samples from golden dataset
python -m evals.run_evals --samples 5

# Upload resulting eval_results.csv to Arize AX:
# Datasets → + New Dataset → Upload CSV → name it "brand-trust-agent-evals"
```

## Project Structure

```
brand-trust-agent/
├── app.py                          # Streamlit frontend
├── agents/
│   ├── brand_research_agent.py     # Agent 1: RAG + grounding score
│   └── campaign_strategy_agent.py  # Agent 2: Campaign generator
├── data/
│   ├── brand_docs/                 # Verdant brand documents (RAG source)
│   │   ├── verdant_brand_guide.txt
│   │   ├── verdant_products.txt
│   │   ├── verdant_sustainability.txt
│   │   └── verdant_poisoned.txt    # Injection demo document
│   └── golden_dataset.csv          # 20-row eval dataset
├── evals/
│   └── run_evals.py                # Arize AX eval runner
├── instrumentation/
│   └── arize_setup.py              # Arize OTel registration
├── requirements.txt
└── .env.example
```

## Arize AX Workflows

### Development Workflow
1. Run `evals/run_evals.py` to generate `eval_results.csv`
2. Upload to Arize AX: **Datasets → + New Dataset**
3. Open **Prompt Playground** — experiment with Agent 1 and Agent 2 prompts
4. Run **LLM Evals** on the dataset: hallucination eval + brand safety eval

### Observability Workflow
1. Run the Streamlit app and trigger each failure mode scenario
2. Open **Arize AX → Projects → brand-trust-agent → Traces**
3. Use **Agent Visibility** to see the 2-agent flow as a flowchart
4. Inspect span attributes: `trust.grounding_score`, `trust.injection_risk`, `trust.risk_level`
5. Note the gap: Agent 1's trust signals don't propagate natively to Agent 2's span

## Product Proposal Context

This demo is designed to support a feature proposal called **Arize Sentinel (Multi-Agent Trust)**:

The core observation: Arize AX today shows both agent spans but does **not** natively:
- Propagate confidence/grounding scores between agents
- Detect prompt injection patterns in retrieved context
- Raise real-time alerts when upstream trust signals drop below threshold

The proposal adds a **Trust Layer** between agents — making trust signals first-class
trace attributes that flow automatically through multi-agent pipelines, turning Arize
from an "observe and react" tool into a "prevent and enforce" platform.

---
Built by Rebecca Riggs  · 2026
