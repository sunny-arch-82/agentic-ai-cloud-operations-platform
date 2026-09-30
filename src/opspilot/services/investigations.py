import asyncio
import time
import uuid

from sqlalchemy import text

from opspilot.core.logging import event
from opspilot.mcp.client import connect_tools
from opspilot.models.llm import make_model
from opspilot.schemas.contracts import Draft, InvestigationReport
from opspilot.services.validation import all_citations
from opspilot.workflows.investigation import InvestigationWorkflow


def persist_start(db, investigation_id, request):
    with db.engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO investigations(investigation_id,status,request)
            VALUES (:id,'running',CAST(:request AS jsonb))"""),
            {"id": investigation_id, "request": request.model_dump_json()},
        )


def persist_report(db, report):
    with db.engine.begin() as conn:
        conn.execute(
            text("""UPDATE investigations SET report=CAST(:report AS jsonb),status=:status,
            updated_at=now() WHERE investigation_id=:id"""),
            {
                "report": report.model_dump_json(),
                "status": report.status,
                "id": report.investigation_id,
            },
        )
        for e in report.evidence:
            conn.execute(
                text("""INSERT INTO evidence_items VALUES (:id,:eid,CAST(:payload AS jsonb))
                ON CONFLICT DO NOTHING"""),
                {
                    "id": report.investigation_id,
                    "eid": e.evidence_id,
                    "payload": e.model_dump_json(),
                },
            )
        for i, a in enumerate(report.tool_activity):
            conn.execute(
                text("""INSERT INTO tool_activity VALUES (:id,:ordinal,CAST(:payload AS jsonb))
                ON CONFLICT DO NOTHING"""),
                {"id": report.investigation_id, "ordinal": i, "payload": a.model_dump_json()},
            )


async def investigate(db, settings, request, model=None, tools=None):
    investigation_id = str(uuid.uuid4())
    await asyncio.to_thread(persist_start, db, investigation_id, request)
    workflow = InvestigationWorkflow(
        request, settings, model or make_model(settings), tools, investigation_id
    )
    try:
        if tools is None:
            async with asyncio.timeout(settings.deadline_seconds):
                async with connect_tools(settings) as connected:
                    workflow.tools = connected
                    state = await workflow.run()
        else:
            state = await workflow.run()
    except Exception as exc:
        state = workflow.last_state
        workflow.failed = True
        workflow.issues.append(f"MCP connection unavailable ({type(exc).__name__})")
    draft = state.get("draft") or Draft(
        observations=[], hypotheses=[], missing_evidence=[], recommended_next_steps=[]
    )
    verdict = state.get("verification")
    if verdict:
        unsupported = set(verdict.unsupported_claims)
        draft = draft.model_copy(
            update={
                "observations": [c for c in draft.observations if c.statement not in unsupported],
                "hypotheses": [c for c in draft.hypotheses if c.statement not in unsupported],
                "recommended_next_steps": [
                    c for c in draft.recommended_next_steps if c.statement not in unsupported
                ],
            }
        )
    verified = bool(verdict and verdict.verdict == "supported" and not verdict.unsupported_claims)
    if not verified:
        # Return captured observations, but never present unverified hypotheses as finalized.
        draft = draft.model_copy(update={"hypotheses": []})
    status = (
        "failed"
        if workflow.failed and not workflow.evidence
        else (
            "completed"
            if verified and not workflow.failed and not any(a.status != "ok" for a in workflow.activity)
            else "incomplete"
        )
    )
    report = InvestigationReport(
        investigation_id=investigation_id,
        question=request.question,
        service=request.service,
        dataset_id=request.dataset_id,
        reference_time=request.reference_time,
        time_window=request.time_window,
        status=status,
        assessment="hypotheses" if draft.hypotheses else "insufficient_evidence",
        observations=draft.observations,
        hypotheses=draft.hypotheses,
        evidence=list(workflow.evidence.values()),
        contradictory_evidence=sorted(
            {i for h in draft.hypotheses for i in h.contradictory_evidence_ids}
        ),
        missing_evidence=list(
            dict.fromkeys(
                draft.missing_evidence
                + workflow.issues
                + (verdict.issues if verdict and verdict.verdict != "supported" else [])
            )
        ),
        recommended_next_steps=draft.recommended_next_steps,
        citations=all_citations(draft),
        verification=verdict,
        tool_activity=workflow.activity,
        model_calls=workflow.model_calls,
        tool_calls=workflow.tool_calls,
        revisions=workflow.revisions,
        duration_ms=round((time.monotonic() - workflow.started) * 1000, 2),
        model=settings.model_id,
        mode=settings.mode,
        token_usage=workflow.model.usage,
        limitations=[
            "Synthetic, sampled operational data; no infrastructure actions executed.",
            "Citation resolution does not establish semantic correctness.",
        ]
        + (
            ["Deterministic offline simulator; this is not an LLM quality measurement."]
            if settings.mode == "demo"
            else []
        ),
    )
    await asyncio.to_thread(persist_report, db, report)
    event(
        "investigation_complete",
        investigation_id=investigation_id,
        status=status,
        duration_ms=report.duration_ms,
        model_calls=report.model_calls,
        tool_calls=report.tool_calls,
    )
    return report


def get_investigation(db, investigation_id):
    rows = db.read(
        "SELECT investigation_id,status,request,report,created_at FROM investigations WHERE investigation_id=:id",
        {"id": investigation_id},
    )
    if not rows:
        return None
    return rows[0]["report"] or {
        "investigation_id": investigation_id,
        "status": rows[0]["status"],
        "message": "Execution is in progress or was interrupted; this release does not resume jobs.",
    }
