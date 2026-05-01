## Arize AX Workflows

### Development
1. Run the 5-campaign series in the app to generate drift data
2. Upload a dataset to **Arize AX → Datasets → + New Dataset** with columns: `cycle`, `question` (brand brief), `input` (brand facts reference), `output` (generated caption)
3. Open **Prompt Playground** → select Hallucination template
4. Map `{input}` → brand facts reference, `{output}` → generated caption
5. Set the judge prompt as a **system prompt** (not user prompt) for accurate results
6. Run evals — compare results across cycles to see grounding decline

### Production Observability
1. Run the app and trigger campaigns from the UI
2. Open **Arize AX → Projects → brand-trust-agent → Traces**
3. Inspect the `vector-retrieval` span to see the evolved query and retrieved chunks
4. Check custom span attributes:
   - On agent spans: `trust.grounding_score`, `trust.injection_risk`, `trust.hallucination_detected`
   - On campaign (CHAIN) spans: `campaign.grounding_score`, `campaign.caption`, `campaign.video_prompt`, `campaign.halted`
5. Use **Agent Graph** view to see the 3-agent flow and where the pipeline halted

## Key Finding

The standard Arize hallucination eval template (user prompt) missed a fabricated material composition claim in Cycle 4 because it checks semantic similarity, not specific numerical facts. Moving the judge prompt to the **system role** fixed this — a meaningful product insight for eval template design.

## Product Proposal: Sentinel

This project supports a product proposal for cross-run drift detection in Arize AX.

The core gap: individual traces show a grounding score. But there is no cross-run alert when that score degrades over time. By Cycle 5, the grounding score had fallen from 0.89 to 0.60 across five weeks — invisible without trend monitoring.

**Proposed features:**
- **Drift threshold monitor** — alert when a tracked metric drops more than X% between consecutive runs
- **Session-linked traces** — group traces from the same content series for trend visibility
- **Trace diff view** — side-by-side comparison of two runs showing attribute changes
- **Email/webhook alert** — notify before the next run executes
