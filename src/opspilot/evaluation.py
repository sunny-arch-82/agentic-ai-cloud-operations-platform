"""Repeatable measurements. Reference validity is never labeled semantic faithfulness."""

import hashlib
import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from opspilot.rag.retrieval import Retriever
from opspilot.schemas.contracts import InvestigationRequest, QueryRequest
from opspilot.services.investigations import investigate
from opspilot.services.query import answer_query


def retrieval_metrics(retrieved: list[str], relevant: list[str], k=5):
    gold = set(relevant)
    if not gold:
        return None
    ranking = list(dict.fromkeys(retrieved))[:k]
    return {
        "recall": len(set(ranking) & gold) / len(gold),
        "reciprocal_rank": next((1 / i for i, item in enumerate(ranking, 1) if item in gold), 0.0),
    }


def manifest(settings, dataset):
    return {
        "recorded_at": datetime.now(UTC).isoformat(),
        "release": "1.0.0-portfolio",
        "python": platform.python_version(),
        "mode": settings.mode,
        "model": settings.model_id,
        "embedding_key": settings.embedding_key,
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "limitations": [
            "Small synthetic authored benchmark; not an independently reviewed production benchmark.",
            "No human semantic groundedness/correctness scores have been measured.",
        ]
        + (
            ["Hashing vectors and deterministic model simulator; not neural semantic/LLM quality."]
            if settings.mode == "demo"
            else []
        ),
    }


async def evaluate_retrieval(db, settings, split="all"):
    path = Path("evals/datasets/golden.json")
    cases = [c for c in json.loads(path.read_text()) if split == "all" or c["split"] == split]
    retriever = Retriever(db, settings)
    result = {**manifest(settings, path), "kind": "retrieval", "split": split, "k": 5, "modes": {}}
    for mode in ["semantic", "lexical", "hybrid"]:
        rows = []
        for case in cases:
            retrieved = await retriever.search(
                case["question"],
                case["service"],
                datetime.fromisoformat(case["reference_time"]),
                mode,
                5,
            )
            sections = [r["section_id"] for r in retrieved]
            metrics = retrieval_metrics(sections, case["relevant_sections"])
            rows.append(
                {
                    "id": case["id"],
                    "answerable": case["answerable"],
                    "sections": sections,
                    "metrics": metrics,
                }
            )
        measured = [r["metrics"] for r in rows if r["metrics"] is not None]
        result["modes"][mode] = {
            "vector_type": "lexical feature hashing"
            if settings.mode == "demo"
            else settings.embedding_model,
            "answerable_cases": len(measured),
            "unanswerable_cases": len(rows) - len(measured),
            "recall_at_5": mean(m["recall"] for m in measured) if measured else None,
            "mrr_at_5": mean(m["reciprocal_rank"] for m in measured) if measured else None,
            "cases": rows,
        }
    return result


async def evaluate_answers(db, settings, split="all"):
    path = Path("evals/datasets/golden.json")
    cases = [c for c in json.loads(path.read_text()) if split == "all" or c["split"] == split]
    rows = []
    for case in cases:
        try:
            answer = await answer_query(
                db,
                settings,
                QueryRequest(
                    question=case["question"],
                    service=case["service"],
                    reference_time=case["reference_time"],
                ),
            )
            valid = set(answer.citations) <= {e.evidence_id for e in answer.evidence}
            rows.append(
                {
                    "id": case["id"],
                    "answerable": case["answerable"],
                    "status": answer.status,
                    "schema_valid": True,
                    "references_resolve": valid,
                    "answer": answer.model_dump(mode="json"),
                    "error": None,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "id": case["id"],
                    "answerable": case["answerable"],
                    "status": "error",
                    "schema_valid": False,
                    "references_resolve": False,
                    "error": type(exc).__name__,
                }
            )
    negatives = [r for r in rows if not r["answerable"]]
    positives = [r for r in rows if r["answerable"]]
    return {
        **manifest(settings, path),
        "kind": "answers",
        "cases": rows,
        "schema_valid_rate": mean(r["schema_valid"] for r in rows),
        "reference_resolution_rate": mean(r["references_resolve"] for r in rows),
        "unanswerable_abstention_rate": mean(
            r["status"] == "insufficient_evidence" for r in negatives
        )
        if negatives
        else None,
        "answerable_response_rate": mean(r["status"] == "answered" for r in positives)
        if positives
        else None,
        "semantic_groundedness": "NOT MEASURED YET",
        "answer_correctness": "NOT MEASURED YET",
    }


def scenario_request(dataset_id="s01"):
    return InvestigationRequest(
        question="Investigate checkout latency and errors; compare dependencies and recent changes.",
        service="checkout",
        dataset_id=dataset_id,
        reference_time="2026-09-01T12:00:00Z",
        time_window={"start": "2026-09-01T11:00:00Z", "end": "2026-09-01T12:00:00Z"},
    )


async def evaluate_investigations(db, settings):
    path = Path("evals/datasets/investigations.json")
    labels = json.loads(path.read_text())  # Only the evaluator can access ground-truth labels.
    rows = []
    for case in labels:
        report = await investigate(db, settings, scenario_request(case["dataset_id"]))
        rows.append(
            {
                "dataset_id": case["dataset_id"],
                "expected_for_manual_review": case["expected"],
                "references_resolve": set(report.citations)
                <= {e.evidence_id for e in report.evidence},
                "budget_respected": report.model_calls <= settings.max_model_calls
                and report.tool_calls <= settings.max_tool_calls,
                "report": report.model_dump(mode="json"),
            }
        )
    return {
        **manifest(settings, path),
        "kind": "investigations",
        "cases": rows,
        "reference_resolution_rate": mean(r["references_resolve"] for r in rows),
        "budget_respected_rate": mean(r["budget_respected"] for r in rows),
        "human_diagnosis_correctness": "NOT MEASURED YET",
        "verifier_quality_improvement": "NOT MEASURED YET",
    }
