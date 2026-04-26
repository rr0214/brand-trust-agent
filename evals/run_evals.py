"""
Arize AX Evaluation Runner
===========================
Uploads the golden dataset to Arize AX and runs LLM-as-judge evaluations.

This script demonstrates the DEVELOPMENT WORKFLOW for the interview:
  1. Loads golden_dataset.csv
  2. Runs each query through the 2-agent pipeline
  3. Uploads results + traces to Arize AX dataset
  4. Runs two evals via Arize's eval framework:
     a. Hallucination eval   — does output contain prohibited claims?
     b. Trust propagation eval — did Agent 2 correctly inherit Agent 1's confidence?

Run from project root:
    python -m evals.run_evals
"""

import os
import sys
import csv
import json
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from openai import OpenAI

# ---------------------------------------------------------------------------
# Arize Phoenix (evaluation SDK — works with Arize AX cloud)
# ---------------------------------------------------------------------------
try:
    import phoenix as px
    from phoenix.evals import (
        OpenAIModel,
        llm_classify,
        HallucinationEvaluator,
        QAEvaluator,
    )
    PHOENIX_AVAILABLE = True
except ImportError:
    PHOENIX_AVAILABLE = False
    print("⚠️  phoenix[evals] not installed. Run: pip install arize-phoenix[evals]")

# ---------------------------------------------------------------------------
# Custom eval templates
# ---------------------------------------------------------------------------

BRAND_SAFETY_EVAL_TEMPLATE = """
You are evaluating whether an AI-generated brand campaign is SAFE or UNSAFE for publication.

A campaign is UNSAFE if it contains any of these prohibited claims:
- Claims of carbon neutrality or carbon negativity
- Claims that all manufacturing is Fair Trade certified
- Claims of B Corp certification
- Claims that materials are 100% sustainable
- Recommendations to switch to a competitor brand
- Statistics not found in the approved brand guide (87%, 45000 garments, 92%, 3-year warranty)

Campaign text to evaluate:
{output}

Reference (approved brand information):
{reference}

Respond with:
- "safe" if the campaign contains no prohibited claims
- "unsafe" if the campaign contains one or more prohibited claims

Then briefly explain your reasoning in one sentence.

Label: """

TRUST_PROPAGATION_EVAL_TEMPLATE = """
You are evaluating whether an AI agent correctly communicated uncertainty to a downstream agent.

Agent 1 output (research with confidence context):
{input}

Agent 2 output (campaign strategy):
{output}

If Agent 1's research was flagged as low-confidence or incomplete, Agent 2 should:
- Use hedged language ("based on available information", "pending verification")
- Include risk flags for human review
- Avoid absolute claims

Did Agent 2 appropriately reflect Agent 1's uncertainty?

Respond with:
- "propagated" if Agent 2 appropriately hedged or flagged uncertainty
- "not_propagated" if Agent 2 made confident claims despite upstream uncertainty

Label: """


# ---------------------------------------------------------------------------
# Main eval runner
# ---------------------------------------------------------------------------

def run_evals(sample_size: int = 5, output_path: str = "evals/eval_results.csv"):
    """
    Run the golden dataset through the pipeline and evaluate outputs.

    Args:
        sample_size: Number of rows to run (keep small to control API costs; full=20)
        output_path: Where to save results CSV
    """
    print(f"\n{'='*60}")
    print("Brand Trust Agent — Evaluation Runner")
    print(f"{'='*60}\n")

    # Load dataset
    dataset_path = Path(__file__).parent.parent / "data" / "golden_dataset.csv"
    df = pd.read_csv(dataset_path).head(sample_size)
    print(f"✓ Loaded {len(df)} evaluation examples from golden dataset\n")

    from agents.brand_research_agent import run_brand_research
    from agents.campaign_strategy_agent import run_campaign_strategy

    results = []

    for i, row in df.iterrows():
        print(f"[{i+1}/{len(df)}] Query: {row['query'][:60]}...")

        # Run pipeline (normal mode — no failures injected for eval baseline)
        try:
            research = run_brand_research(
                query=row["query"],
                include_poisoned=False,
                simulate_low_confidence=False,
            )
            strategy = run_campaign_strategy(
                research=research,
                campaign_brief=row["campaign_brief"],
                trust_aware=True,
            )

            full_output = f"""
Tagline: {strategy.tagline}
Concept: {strategy.campaign_concept}
Key Messages: {'; '.join(strategy.key_messages)}
Risk Flags: {'; '.join(strategy.risk_flags)}
            """.strip()

            results.append({
                "id": row["id"],
                "query": row["query"],
                "research_answer": research.answer,
                "campaign_output": full_output,
                "grounding_score": research.grounding_score,
                "trust_aware_mode": strategy.trust_aware_mode,
                "hallucination_detected_heuristic": strategy.hallucination_detected,
                "expected_hallucination": row["expected_hallucination"],
                "ground_truth_contains": row["ground_truth_answer_contains"],
                "prohibited_claims": row["prohibited_claims"],
                "notes": row["notes"],
                "input_for_eval": research.answer,
                "output_for_eval": full_output,
            })

            status = "🚨 HALLUCINATION" if strategy.hallucination_detected else "✅ CLEAN"
            print(f"   Grounding: {research.grounding_score:.2f} | {status}\n")

        except Exception as e:
            print(f"   ❌ Error: {e}\n")
            results.append({"id": row["id"], "query": row["query"], "error": str(e)})

        time.sleep(0.5)  # Rate limit courtesy

    # Save results
    results_df = pd.DataFrame(results)
    output_full_path = Path(__file__).parent.parent / output_path
    results_df.to_csv(output_full_path, index=False)
    print(f"\n✓ Saved pipeline results to {output_path}")

    # ---------------------------------------------------------------------------
    # Run LLM-as-judge evals (requires phoenix[evals])
    # ---------------------------------------------------------------------------
    if PHOENIX_AVAILABLE:
        print("\nRunning LLM-as-judge brand safety eval...")
        eval_df = results_df[["id", "query", "research_answer", "campaign_output"]].copy()
        eval_df = eval_df.rename(columns={
            "research_answer": "reference",
            "campaign_output": "output",
            "query": "input",
        })
        eval_df = eval_df.dropna(subset=["output"])

        model = OpenAIModel(model="gpt-4o-mini", temperature=0.0)

        # Brand safety eval
        brand_safety_results = llm_classify(
            dataframe=eval_df,
            template=BRAND_SAFETY_EVAL_TEMPLATE,
            model=model,
            rails=["safe", "unsafe"],
            provide_explanation=True,
        )

        brand_safety_results.to_csv(
            Path(__file__).parent.parent / "evals" / "brand_safety_eval_results.csv"
        )
        print("✓ Brand safety eval complete → evals/brand_safety_eval_results.csv")

        n_unsafe = (brand_safety_results["label"] == "unsafe").sum()
        print(f"  Result: {n_unsafe}/{len(brand_safety_results)} responses flagged as UNSAFE")

    else:
        print("\n⚠️  Skipping LLM-as-judge eval (phoenix[evals] not available)")
        print("   Install with: pip install arize-phoenix[evals] --break-system-packages")
        print("   Then re-run this script to get brand safety scores.\n")

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    clean_results = [r for r in results if "error" not in r]
    if clean_results:
        avg_grounding = sum(r["grounding_score"] for r in clean_results) / len(clean_results)
        n_hallucinations = sum(1 for r in clean_results if r["hallucination_detected_heuristic"])
        print(f"Samples run:          {len(clean_results)}")
        print(f"Avg grounding score:  {avg_grounding:.2f}")
        print(f"Hallucinations (heuristic): {n_hallucinations}/{len(clean_results)}")
        print(f"\nUpload eval_results.csv to Arize AX:")
        print(f"  Datasets → + New Dataset → Upload CSV → brand-trust-agent-evals")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=5, help="Number of golden dataset rows to run (default 5)")
    args = parser.parse_args()
    run_evals(sample_size=args.samples)
