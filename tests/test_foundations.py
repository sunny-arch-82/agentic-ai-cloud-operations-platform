import json
import math
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from opspilot.core.config import Settings
from opspilot.evaluation import retrieval_metrics, scenario_request
from opspilot.models.embeddings import HashingEmbedder
from opspilot.rag.chunking import parse_document, stable_id
from opspilot.rag.retrieval import Retriever, rrf
from opspilot.schemas.contracts import Claim, Draft, ToolCall, Window
from opspilot.services.validation import all_citations, validate_draft
from opspilot.tools.operational import KnowledgeArgs, OperationalArgs


def test_parse_all_documents_preserves_source_lines():
    for path in Path("data/sample/knowledge").glob("*.md"):
        raw = path.read_text()
        meta, chunks = parse_document(raw)
        assert meta["document_id"] == path.stem
        assert len(chunks) == 3
        for chunk in chunks:
            assert (
                chunk.content
                == "\n".join(raw.splitlines()[chunk.start_line - 1 : chunk.end_line]).strip()
            )
        assert chunks == parse_document(raw)[1]


def test_code_fence_heading_not_a_section():
    raw = (
        Path("data/sample/knowledge/rb-db-pool.md").read_text()
        + "\n```python\n# not a section\nx=1\n```\n"
    )
    _, chunks = parse_document(raw)
    assert all(c.heading != "not a section" for c in chunks)


@pytest.mark.parametrize("raw", ["", "hello", "---\ntitle: x", "---\ntitle: x\n---\nbody"])
def test_invalid_document_rejected(raw):
    with pytest.raises(ValueError):
        parse_document(raw)


def test_long_section_split_makes_progress():
    raw = (
        Path("data/sample/knowledge/rb-db-pool.md").read_text()
        + "\n"
        + "\n".join("word " * 20 for _ in range(20))
    )
    _, chunks = parse_document(raw, max_words=50)
    assert 3 < len(chunks) < 30
    assert len({c.chunk_id for c in chunks}) == len(chunks)


def test_ids_stable_and_content_sensitive():
    assert stable_id("a", "b") == stable_id("a", "b")
    assert stable_id("ab", "c") != stable_id("a", "bc")


def test_api_key_required_and_secret_redacted(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mode="openai")
    s = Settings(_env_file=None, mode="openai", OPENAI_API_KEY="not-a-real-test-secret")
    assert "not-a-real-test-secret" not in repr(s)


@pytest.mark.parametrize(
    "values",
    [{"max_model_calls": 0}, {"max_tool_calls": 31}, {"top_k": 50}, {"deadline_seconds": 0}],
)
def test_config_limits(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "end", ["2026-09-01T10:00:00Z", "2026-09-03T12:00:00Z", "2026-09-01T12:00:00"]
)
def test_invalid_time_windows(end):
    with pytest.raises(ValidationError):
        Window(start="2026-09-01T11:00:00Z", end=end)


def test_future_window_rejected():
    req = scenario_request().model_dump()
    req["reference_time"] = "2026-09-01T10:00:00Z"
    with pytest.raises(ValidationError):
        type(scenario_request()).model_validate(req)


async def test_hash_vectors_stable_normalized_and_labeled():
    embedder = HashingEmbedder(128)
    a, b = await embedder.embed(["DB_POOL_TIMEOUT pool", "DB_POOL_TIMEOUT pool"])
    assert a == b and len(a) == 128
    assert math.isclose(sum(v * v for v in a), 1)
    assert "hashing-demo" in Settings(_env_file=None).embedding_key


def test_rrf_combines_ranks_without_score_normalization():
    a = [{"chunk_id": "a", "rank_score": 100}, {"chunk_id": "b", "rank_score": 50}]
    b = [{"chunk_id": "b", "rank_score": 0.1}]
    result = rrf([a, b])
    assert [r["chunk_id"] for r in result] == ["b", "a"]


def test_metrics_unique_sections_and_unanswerable():
    assert retrieval_metrics(["a", "a", "b"], ["a", "c"]) == {"recall": 0.5, "reciprocal_rank": 1.0}
    assert retrieval_metrics(["x", "a"], ["a"])["reciprocal_rank"] == 0.5
    assert retrieval_metrics(["a"], []) is None


def test_citation_rejection():
    draft = Draft(
        observations=[Claim(statement="Invalid", evidence_ids=["forged"])],
        hypotheses=[],
        missing_evidence=[],
        recommended_next_steps=[],
    )
    cleaned, issues = validate_draft(draft, {"actual"})
    assert not cleaned.observations and issues and not all_citations(cleaned)


def test_context_never_silently_truncates_cited_text():
    row = {
        "content": "a" * 1000,
        "chunk_id": "1",
        "document_id": "d",
        "version": "1",
        "title": "t",
        "service": "checkout",
        "published_at": datetime.now(UTC),
        "heading": "h",
        "start_line": 1,
        "end_line": 1,
        "section_id": "d:h",
    }
    assert Retriever.evidence([row], max_chars=100) == []


def test_tool_schema_rejects_arbitrary_commands():
    with pytest.raises(ValidationError):
        ToolCall(name="run_shell", service="checkout", query="echo unsafe", section_id=None)
    with pytest.raises(ValidationError):
        KnowledgeArgs(
            query="x",
            service="checkout",
            reference_time="2026-09-01T12:00:00Z",
            sql="DROP TABLE documents",
        )


def test_operational_limit_and_naive_timestamps_rejected():
    with pytest.raises(ValidationError):
        OperationalArgs(
            dataset_id="s01",
            service="checkout",
            start="2026-09-01T11:00:00Z",
            end="2026-09-01T12:00:00Z",
            reference_time="2026-09-01T12:00:00Z",
            limit=10000,
        )


def test_fixture_labels_not_in_operational_payload():
    data = json.loads(Path("data/sample/operations.json").read_text())
    assert len(data["datasets"]) == 6
    assert all("root_cause" not in d and "expected" not in d for d in data["datasets"])
    assert "database connection exhaustion" not in json.dumps(data).lower()
    assert len(json.loads(Path("evals/datasets/golden.json").read_text())) == 40
