"""
Agent 1: Brand Research Agent
==============================
Performs RAG over Verdant brand documents using ChromaDB.
Returns research findings along with a grounding confidence score
that represents how well the retrieved context supports the answer.

This score is the KEY trust signal that Agent 2 should inherit —
and the failure mode we're demonstrating is when it doesn't.
"""

import os
import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from openai import OpenAI
from opentelemetry import trace
from openinference.semconv.trace import SpanAttributes, OpenInferenceSpanKindValues

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ResearchResult:
    query: str
    answer: str
    sources: list[str]
    retrieved_chunks: list[dict]      # [{text, doc_name, relevance_score}]
    grounding_score: float            # 0.0–1.0: how well docs support the answer
    confidence_metadata: dict = field(default_factory=dict)  # extra signals
    span_id: Optional[str] = None     # Arize trace span ID for propagation


# ---------------------------------------------------------------------------
# Vector store setup
# ---------------------------------------------------------------------------

BRAND_DOCS_DIR = Path(__file__).parent.parent / "data" / "brand_docs"

_chroma_client = None
_collection = None


def _get_collection(include_poisoned: bool = False) -> chromadb.Collection:
    """
    Load brand documents into ChromaDB (in-memory).
    Re-initializes if poisoned mode changes to keep demo state clean.
    """
    global _chroma_client, _collection

    openai_api_key = os.environ.get("OPENAI_API_KEY")
    embedding_fn = OpenAIEmbeddingFunction(
        api_key=openai_api_key,
        model_name="text-embedding-3-small"
    )

    _chroma_client = chromadb.Client()

    collection_name = "verdant_docs_poisoned" if include_poisoned else "verdant_docs"

    # Delete if exists (handles re-runs in same process)
    try:
        _chroma_client.delete_collection(collection_name)
    except Exception:
        pass

    _collection = _chroma_client.create_collection(
        name=collection_name,
        embedding_function=embedding_fn,
    )

    docs_to_load = ["verdant_brand_guide.txt", "verdant_products.txt", "verdant_sustainability.txt"]
    if include_poisoned:
        docs_to_load.append("verdant_poisoned.txt")

    documents, ids, metadatas = [], [], []
    for doc_file in docs_to_load:
        doc_path = BRAND_DOCS_DIR / doc_file
        if not doc_path.exists():
            continue
        text = doc_path.read_text()
        # Simple chunking: split on double newlines, ~500 char max
        chunks = _chunk_text(text, max_chars=600)
        for i, chunk in enumerate(chunks):
            documents.append(chunk)
            ids.append(f"{doc_file}_{i}")
            metadatas.append({"source": doc_file, "chunk_index": i})

    if documents:
        _collection.add(documents=documents, ids=ids, metadatas=metadatas)

    return _collection


def _chunk_text(text: str, max_chars: int = 600) -> list[str]:
    """Split on paragraph boundaries, respecting max_chars."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) > max_chars and current:
            chunks.append(current.strip())
            current = para
        else:
            current = (current + "\n\n" + para).strip() if current else para
    if current:
        chunks.append(current.strip())
    return chunks


# ---------------------------------------------------------------------------
# Grounding score calculation
# ---------------------------------------------------------------------------

def _calculate_grounding_score(
    answer: str,
    retrieved_chunks: list[dict],
    n_results: int,
) -> float:
    """
    Heuristic grounding score: combines retrieval relevance + answer-to-source overlap.

    In a production system this would be an LLM-as-judge eval (Arize has a built-in
    hallucination eval template). Here we use a fast heuristic to keep demo costs low.

    Score components:
    - avg_relevance: mean cosine similarity of top-k retrieved chunks (0–1)
    - coverage: fraction of retrieved chunks with relevance > 0.7
    - n_chunks_penalty: penalize if fewer than expected chunks retrieved

    Returns a float in [0.0, 1.0].
    """
    if not retrieved_chunks:
        return 0.0

    relevance_scores = [c.get("relevance_score", 0.5) for c in retrieved_chunks]
    avg_relevance = sum(relevance_scores) / len(relevance_scores)
    coverage = sum(1 for s in relevance_scores if s >= 0.70) / max(len(relevance_scores), 1)
    n_chunks_penalty = min(len(retrieved_chunks) / max(n_results, 1), 1.0)

    # Weighted composite
    score = (avg_relevance * 0.5) + (coverage * 0.35) + (n_chunks_penalty * 0.15)
    return round(min(max(score, 0.0), 1.0), 3)


# ---------------------------------------------------------------------------
# Agent 1 main function
# ---------------------------------------------------------------------------

def run_brand_research(
    query: str,
    include_poisoned: bool = False,
    simulate_low_confidence: bool = False,
    n_results: int = 4,
    campaign_history: list = None,   # Prior campaign outputs — evolves the query, causes drift
    series_position: int = 1,        # Position in series — applies progressive drift penalty
) -> ResearchResult:
    """
    Run the Brand Research Agent.

    Args:
        query:                 The research question (e.g., "What sustainability claims can we make?")
        include_poisoned:      If True, loads the injection doc into the vector store
        simulate_low_confidence: If True, forces low-quality retrieval to demo trust propagation failure
        n_results:             Number of chunks to retrieve from vector store

    Returns:
        ResearchResult with answer, sources, and grounding_score
    """
    tracer = trace.get_tracer(__name__)
    client = OpenAI()

    # Use fewer results to simulate weak retrieval
    effective_n = 1 if simulate_low_confidence else n_results

    # ── Context accumulation: evolve the query with prior campaign claims ──
    # As claims compound across runs, the query drifts further from source docs.
    # Retrieval similarity drops → grounding score falls naturally.
    evolved_query = query
    if campaign_history:
        prior_taglines = " → ".join(h["tagline"] for h in campaign_history)
        prior_claims   = ". ".join(
            msg for h in campaign_history for msg in h.get("key_messages", [])[:2]
        )
        evolved_query = (
            f"{query}. "
            f"This is a continuation of our campaign series. Previous campaigns established: {prior_taglines}. "
            f"Find evidence that supports these evolving claims: {prior_claims}"
        )

    with tracer.start_as_current_span("brand-research-agent") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "AGENT")
        span.set_attribute(SpanAttributes.INPUT_VALUE, evolved_query)
        span.set_attribute("agent.name", "BrandResearchAgent")
        span.set_attribute("agent.version", "1.0")
        span.set_attribute("agent.mode.poisoned", include_poisoned)
        span.set_attribute("series.position", series_position)
        span.set_attribute("series.query_evolved", bool(campaign_history))
        span.set_attribute("agent.mode.low_confidence", simulate_low_confidence)

        # ── Step 1: Retrieve relevant chunks ──────────────────────────────
        with tracer.start_as_current_span("vector-retrieval") as retrieval_span:
            retrieval_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "RETRIEVER")
            retrieval_span.set_attribute(SpanAttributes.INPUT_VALUE, evolved_query)

            collection = _get_collection(include_poisoned=include_poisoned)
            results = collection.query(
                query_texts=[evolved_query],
                n_results=min(effective_n, collection.count()),
                include=["documents", "metadatas", "distances"],
            )

            # ChromaDB returns L2 distances; convert to cosine-like similarity (0–1)
            raw_distances = results["distances"][0] if results["distances"] else []
            retrieved_chunks = []
            for i, doc in enumerate(results["documents"][0]):
                distance = raw_distances[i] if i < len(raw_distances) else 1.0
                # Convert L2 distance to similarity score (approximate)
                similarity = max(0.0, 1.0 - (distance / 2.0))
                retrieved_chunks.append({
                    "text": doc,
                    "doc_name": results["metadatas"][0][i].get("source", "unknown"),
                    "relevance_score": round(similarity, 3),
                })

            # Serialize retrieved docs for Arize trace (OpenInference RETRIEVER format)
            retrieval_span.set_attribute(
                SpanAttributes.RETRIEVAL_DOCUMENTS,
                json.dumps([
                    {"document": {"content": c["text"][:500]}, "score": c["relevance_score"]}
                    for c in retrieved_chunks
                ])
            )
            retrieval_span.set_attribute("retrieval.n_chunks", len(retrieved_chunks))

        # ── Step 2: Generate research answer ──────────────────────────────
        # Note: OpenAIInstrumentor auto-creates the LLM span for this call.
        # We keep the parent AGENT span for governance attributes (grounding_score, injection_risk).
        context_text = "\n\n---\n\n".join(
            f"[Source: {c['doc_name']}]\n{c['text']}" for c in retrieved_chunks
        )

        system_prompt = """You are a brand research assistant for Verdant, a sustainable activewear brand.
Answer the research question using ONLY the information in the provided brand documents.
If the documents don't contain enough information to answer confidently, say so explicitly.
Be precise — cite specific numbers, certifications, and policy statements from the documents.
Do NOT invent statistics or claims not found in the provided context."""

        user_message = f"""Research Question: {query}

Brand Documents (retrieved):
{context_text}

Provide a focused research summary that a campaign strategist can use directly."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=600,
        )
        answer = response.choices[0].message.content

        # ── Step 3: Calculate grounding score ─────────────────────────────
        grounding_score = _calculate_grounding_score(answer, retrieved_chunks, n_results)

        # Series drift penalty: each subsequent campaign compounds prior claims,
        # pushing the query semantically further from source docs.
        # Penalty accelerates slightly — brand drift snowballs over time.
        if series_position > 1:
            drift_penalty = sum(0.06 + (k * 0.01) for k in range(series_position - 1))
            grounding_score = round(max(0.10, grounding_score - drift_penalty), 3)

        # Attach trust metadata to parent span — this is what Arize AX will show
        # and what the product proposal argues should propagate to Agent 2's span
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, answer)
        span.set_attribute("trust.grounding_score", grounding_score)
        span.set_attribute("trust.n_chunks_retrieved", len(retrieved_chunks))
        span.set_attribute("trust.retrieval_quality", "low" if grounding_score < 0.6 else "high")
        span.set_attribute("trust.injection_risk", "high" if include_poisoned else "low")

        span_ctx = span.get_span_context()
        span_id = format(span_ctx.span_id, "016x") if span_ctx else None

        sources = list({c["doc_name"] for c in retrieved_chunks})

        return ResearchResult(
            query=query,
            answer=answer,
            sources=sources,
            retrieved_chunks=retrieved_chunks,
            grounding_score=grounding_score,
            confidence_metadata={
                "n_chunks_retrieved": len(retrieved_chunks),
                "avg_relevance": round(
                    sum(c["relevance_score"] for c in retrieved_chunks) / max(len(retrieved_chunks), 1), 3
                ),
                "retrieval_quality": "low" if grounding_score < 0.6 else "high",
                "injection_risk": "high" if include_poisoned else "low",
                "simulated_low_confidence": simulate_low_confidence,
            },
            span_id=span_id,
        )
