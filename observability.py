"""Per-request observations and small, explicitly scoped evaluation checks.

Quality scores that require a judge are intentionally not inferred from citations
or Knowledge Base similarity scores.
"""

import os
import re
from math import isfinite
from pathlib import PurePosixPath

from rag_client import RETRIEVAL_K


GOLDEN_SOURCES = {
    "what remains outstanding before the project atlas pilot can launch?": {
        "project-atlas-status.md"
    },
}


def model_cost_estimate(metrics: dict | None) -> tuple[float | None, str]:
    """Estimate model inference only, using user-supplied USD / million rates."""
    if metrics is None or not metrics.get("model_calls"):
        return 0.0, "No model call. Other AWS service charges are excluded."
    names = (
        "ATLAS_INPUT_USD_PER_MILLION",
        "ATLAS_OUTPUT_USD_PER_MILLION",
        "ATLAS_CACHE_READ_USD_PER_MILLION",
        "ATLAS_CACHE_WRITE_USD_PER_MILLION",
    )
    try:
        rates = [float(os.environ[name]) for name in names]
        if any(not isfinite(rate) or rate < 0 for rate in rates):
            raise ValueError("negative rate")
    except (KeyError, ValueError):
        return None, "Set all four ATLAS_*_USD_PER_MILLION rates for a model-only estimate."
    counts = (
        metrics.get("input_tokens", 0),
        metrics.get("output_tokens", 0),
        metrics.get("cache_read_tokens", 0),
        metrics.get("cache_write_tokens", 0),
    )
    return sum(count * rate for count, rate in zip(counts, rates)) / 1_000_000, (
        "Estimate from configured model token rates; excludes Knowledge Base, "
        "S3 Vectors, S3, DynamoDB, AgentCore Memory, and any future evaluator or reranker."
    )


def build_report(
    request: str,
    answer: str | None = None,
    sources: list[dict] | None = None,
    task_result: dict | None = None,
    metrics: dict | None = None,
    *,
    status: str = "success",
    error: str | None = None,
    rag_attempted: bool | None = None,
    error_stage: str | None = None,
) -> dict:
    """Build one report. ``None`` means unmeasured, never zero by assumption."""
    sources = sources or []
    cost, cost_note = model_cost_estimate(metrics)
    if status == "error" and metrics is None:
        cost, cost_note = None, "N/A: token usage was not returned before the failure."
    attempted_rag = (metrics is not None) if rag_attempted is None else rag_attempted
    source_rows = []
    for index, source in enumerate(sources, 1):
        source_rows.append({
            "rank": index,
            "uri": source.get("location", {}).get("s3Location", {}).get("uri"),
            "retrieval_score": source.get("score"),
        })

    question = " ".join(request.strip().lower().split())
    expected = GOLDEN_SOURCES.get(question)
    found = {
        PurePosixPath(row["uri"]).name for row in source_rows if row["uri"]
    }
    recall = (
        len(expected & found) / len(expected)
        if expected and attempted_rag and status != "error" else None
    )
    citations = sorted({int(value) for value in re.findall(r"\[(\d+)\]", answer or "")})
    invalid_citations = [number for number in citations if number > len(sources) or number < 1]
    is_answer = metrics is not None and task_result is None and status == "success"
    tool_requested = (
        bool(metrics.get("trace", {}).get("tool_request")) if metrics else None
    )
    tool_succeeded = bool(task_result is not None and status == "success")

    return {
        "status": status,
        "error": error,
        "error_stage": error_stage,
        "system": {
            "backend_latency_ms": metrics.get("total_ms") if metrics else None,
            "memory_ms": metrics.get("memory_ms") if metrics else None,
            "retrieval_ms": metrics.get("retrieval_ms") if metrics else None,
            "model_ms": metrics.get("model_ms") if metrics else None,
            "bedrock_reported_latency_ms": metrics.get("model_service_ms") if metrics else None,
            "ttft_ms": metrics.get("ttft_ms") if metrics else None,
            "first_tool_event_ms": metrics.get("first_tool_event_ms") if metrics else None,
            "tool_ms": metrics.get("tool_ms") if metrics else None,
            "uncached_input_tokens": metrics.get("input_tokens") if metrics else None,
            "cache_read_tokens": metrics.get("cache_read_tokens") if metrics else None,
            "cache_write_tokens": metrics.get("cache_write_tokens") if metrics else None,
            "output_tokens": metrics.get("output_tokens") if metrics else None,
            "approx_output_tokens_per_second": metrics.get("output_tokens_per_second") if metrics else None,
            "cache_reuse_percent": metrics.get("cache_reuse_pct") if metrics else None,
            "estimated_model_usd": cost,
            "cost_note": cost_note,
        },
        "rag": {
            "attempted": attempted_rag,
            "retrieval_succeeded": (
                True if sources else False if attempted_rag and status == "success" else None
            ),
            "returned_chunks": len(sources) if attempted_rag else None,
            "source_documents": metrics.get("source_documents") if metrics else None,
            "retrieved": source_rows,
            "retrieval_k": RETRIEVAL_K,
            "recall_at_k": recall,
            "recall_note": (
                "Compared retrieved results with the known required document for this exact demo question. "
                "Other questions need labelled relevant documents."
                if expected else "N/A: no labelled relevant documents for this request."
            ),
            "reranker_score": None,
            "reranker_note": "N/A: no reranker is configured.",
            "context_relevance": None,
            "context_relevance_note": "N/A: requires a relevance evaluator or labelled dataset.",
        },
        "answer": {
            "citation_numbers": citations if is_answer else None,
            "invalid_citation_numbers": invalid_citations if is_answer else None,
            "citation_check": (
                "No numeric source citations" if not citations else
                "Invalid source number" if invalid_citations else "Source numbers in range"
            ) if is_answer else None,
            "faithfulness": None,
            "groundedness": None,
            "answer_relevance": None,
            "hallucination_rate": None,
            "quality_note": (
                "N/A: these need a source-aware evaluator. Citation syntax "
                "alone does not prove a claim is supported."
                if is_answer else "N/A: no generated informational answer to evaluate."
            ),
        },
        "agent": {
            "model_calls": metrics.get("model_calls") if metrics else 0,
            "tool_calls": metrics.get("tool_calls") if metrics else 0,
            "tool_requested": tool_requested,
            "tool_succeeded": tool_succeeded if tool_requested else None,
            "tool_failed": (not tool_succeeded) if tool_requested else None,
            "application_retries": 0 if metrics else None,
            "agent_loop_count": 0 if metrics else None,
            "task_recorded": bool(task_result) if tool_requested else None,
            "task_created": task_result.get("created") if task_result else None,
            "duplicate_avoided": metrics.get("duplicate_avoided") if metrics else None,
            "task_note": "Task recorded means created or returned; underlying work is not complete.",
        },
        "memory": {
            "conversation_turns_loaded": metrics.get("conversation_turns_loaded") if metrics else None,
            "episodes_loaded": metrics.get("episodes_loaded") if metrics else None,
            "personal_facts_loaded": metrics.get("personal_facts_loaded") if metrics else None,
            "personal_facts_learned": metrics.get("personal_facts_learned", []) if metrics else [],
            "conversation_saved": metrics.get("conversation_saved") if metrics else None,
            "conversation_save_error": metrics.get("conversation_save_error") if metrics else None,
            "note": "Episode extraction is asynchronous; counts show records retrieved for this request.",
        },
    }


def session_summary(reports: list[dict]) -> dict:
    """Rates are for this Streamlit browser session, not production traffic."""
    count = len(reports)
    attempted = [
        report for report in reports
        if report["rag"]["retrieval_succeeded"] is not None
    ]
    tools = [report for report in reports if report["agent"]["tool_requested"]]
    return {
        "transactions": count,
        "retrieval_outcome_unknown": sum(
            r["rag"]["attempted"] and r["rag"]["retrieval_succeeded"] is None
            for r in reports
        ),
        "error_rate_percent": 100 * sum(r["status"] == "error" for r in reports) / count if count else None,
        "retrieval_success_rate_percent": (
            100 * sum(r["rag"]["retrieval_succeeded"] for r in attempted) / len(attempted)
            if attempted else None
        ),
        "tool_success_rate_percent": (
            100 * sum(r["agent"]["tool_succeeded"] for r in tools) / len(tools)
            if tools else None
        ),
        "hallucination_rate_percent": None,
    }
