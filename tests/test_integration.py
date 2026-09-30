from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

from opspilot.api.app import create_app
from opspilot.evaluation import scenario_request
from opspilot.mcp.client import connect_tools
from opspilot.rag.ingestion import ingest
from opspilot.rag.retrieval import Retriever
from opspilot.services.investigations import get_investigation, investigate
from opspilot.tools.operational import OperationalTools

pytestmark = pytest.mark.integration


def args(dataset="s01", service="checkout"):
    return {
        "dataset_id": dataset,
        "service": service,
        "start": "2026-09-01T11:00:00Z",
        "end": "2026-09-01T12:00:00Z",
        "reference_time": "2026-09-01T12:00:00Z",
    }


def test_migration_and_vector_extension(db):
    assert db.read("SELECT version_num FROM alembic_version")[0]["version_num"] == "0001"
    assert db.read("SELECT extversion FROM pg_extension WHERE extname='vector'")
    assert db.read("SELECT '[1,0]'::vector <=> '[1,0]'::vector AS distance")[0]["distance"] == 0


async def test_ingestion_idempotency(db, integration_settings):
    before = db.read("SELECT count(*) AS n FROM chunks")[0]["n"]
    await ingest(db, integration_settings)
    assert db.read("SELECT count(*) AS n FROM chunks")[0]["n"] == before == 72


@pytest.mark.parametrize("mode", ["semantic", "lexical", "hybrid"])
async def test_retrieval_modes(db, integration_settings, mode):
    result = await Retriever(db, integration_settings).search(
        "DB_POOL_TIMEOUT", "checkout", datetime(2026, 9, 1, tzinfo=UTC), mode
    )
    assert result and any(r["document_id"] == "rb-db-pool" for r in result)


async def test_metadata_scope_and_future_filter(db, integration_settings):
    retriever = Retriever(db, integration_settings)
    result = await retriever.search(
        "inventory reservations", "payments", datetime(2026, 9, 1, tzinfo=UTC)
    )
    assert all(r["service"] in {"payments", "postgres", "global"} for r in result)
    assert (
        await retriever.search("DB_POOL_TIMEOUT", "checkout", datetime(2026, 1, 1, tzinfo=UTC))
        == []
    )


def test_readonly_query_transaction(db):
    with pytest.raises(DBAPIError):
        db.read("DELETE FROM services WHERE service='never-existing-test'")


async def test_metric_percentiles_and_coverage(db, integration_settings):
    result = await OperationalTools(db, integration_settings).call("fetch_service_metrics", args())
    series = result.evidence[0].data["series"]
    lat = next(
        r for r in series if r["period"] == "current" and r["metric"] == "request_duration_ms"
    )
    assert lat["sample_count"] == 150 and lat["observed_minutes"] == 30
    assert 1900 < lat["p95"] < 1916


async def test_log_truncation_and_counts(db, integration_settings):
    result = await OperationalTools(db, integration_settings).call(
        "inspect_logs", dict(args(), limit=2)
    )
    item = result.evidence[0]
    assert len(item.data["rows"]) == 2 and item.data["truncated"]
    assert sum(r["count"] for r in item.data["code_counts"]) == item.data["total_rows"]


async def test_missing_telemetry_is_explicit(db, integration_settings):
    result = await OperationalTools(db, integration_settings).call(
        "fetch_service_metrics", args("s05")
    )
    assert result.warnings and result.evidence[0].data["sample_count"] == 0


@pytest.mark.parametrize("name", ["inspect_logs", "fetch_service_metrics", "list_service_changes"])
async def test_future_reference_is_rejected(db, integration_settings, name):
    with pytest.raises(ValueError):
        await OperationalTools(db, integration_settings).call(
            name, dict(args(), reference_time="2026-09-02T12:00:00Z")
        )


async def test_mcp_real_transport_all_tools_and_schemas(db, integration_settings):
    async with connect_tools(integration_settings) as tools:
        advertised = await tools.list_tools()
        assert len(advertised) == 6 and all(t.inputSchema and t.outputSchema for t in advertised)
        for name in ["inspect_logs", "fetch_service_metrics", "list_service_changes"]:
            assert (await tools.call(name, args())).evidence
        for name in ["search_knowledge", "search_incidents"]:
            assert (
                await tools.call(
                    name,
                    {
                        "query": "DB_POOL_TIMEOUT",
                        "service": "checkout",
                        "reference_time": "2026-09-01T12:00:00Z",
                    },
                )
            ).evidence
        section = await tools.call(
            "get_document_section",
            {
                "section_id": "rb-db-pool:interpretation",
                "service": "checkout",
                "reference_time": "2026-09-01T12:00:00Z",
            },
        )
        assert section.evidence[0].data["section_id"] == "rb-db-pool:interpretation"


@pytest.mark.parametrize("dataset", ["s01", "s02", "s03", "s04", "s05", "s06"])
async def test_investigation_scenarios(db, integration_settings, dataset):
    # Real database + LangGraph with direct tools; dedicated test above validates MCP.
    report = await investigate(
        db,
        integration_settings,
        scenario_request(dataset),
        tools=OperationalTools(db, integration_settings),
    )
    assert set(report.citations) <= {e.evidence_id for e in report.evidence}
    assert report.model_calls <= integration_settings.max_model_calls
    assert report.tool_calls <= integration_settings.max_tool_calls
    assert get_investigation(db, report.investigation_id)["status"] == report.status
    if dataset == "s05":
        assert report.status == "incomplete" and not report.hypotheses and report.missing_evidence
    else:
        assert report.status == "completed", report.missing_evidence
        assert report.hypotheses
    if dataset == "s06":
        assert report.contradictory_evidence
        assert any("after" in o.statement for o in report.observations)


def test_api_end_to_end_and_readiness(db, integration_settings):
    with TestClient(create_app(integration_settings, db)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200
        assert client.post("/query", json={"question": "x"}).status_code == 422
        assert client.get("/investigations/00000000-0000-0000-0000-000000000000").status_code == 404
        answer = client.post(
            "/query",
            json={
                "question": "DB_POOL_TIMEOUT",
                "service": "checkout",
                "reference_time": "2026-09-01T12:00:00Z",
            },
        )
        assert answer.status_code == 200 and answer.json()["citations"]
        result = client.post("/investigations", json=scenario_request().model_dump(mode="json"))
        assert result.status_code == 201, result.text
        report = result.json()
        assert report["status"] == "completed", report["missing_evidence"]
        assert client.get(f"/investigations/{report['investigation_id']}").json() == report
        assert result.headers["X-Request-ID"]


async def test_invalid_tool_output_cannot_masquerade_as_evidence(db, integration_settings):
    class Broken:
        async def call(self, *args):
            return {"fake": "not a ToolResult"}

    report = await investigate(db, integration_settings, scenario_request(), tools=Broken())
    assert report.status != "completed" and not report.evidence
