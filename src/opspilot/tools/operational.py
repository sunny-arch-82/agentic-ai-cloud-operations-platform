"""The same typed read-only implementations serve MCP and direct integration tests."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from opspilot.rag.chunking import stable_id
from opspilot.rag.retrieval import Retriever
from opspilot.schemas.contracts import Evidence, Service, StrictModel, Window


class KnowledgeArgs(StrictModel):
    query: str = Field(min_length=1, max_length=2000)
    service: Service
    reference_time: AwareDatetime
    mode: Literal["semantic", "lexical", "hybrid"] = "hybrid"
    limit: int = Field(default=5, ge=1, le=10)


class SectionArgs(StrictModel):
    section_id: str = Field(min_length=1, max_length=150)
    service: Service
    reference_time: AwareDatetime


class OperationalArgs(StrictModel):
    dataset_id: str = Field(pattern=r"^s0[1-6]$")
    service: Service
    start: AwareDatetime
    end: AwareDatetime
    reference_time: AwareDatetime
    limit: int = Field(default=100, ge=1, le=200)

    @model_validator(mode="after")
    def window(self):
        Window(start=self.start, end=self.end)
        if self.end > self.reference_time:
            raise ValueError("Requested data exceeds reference time")
        return self


class ToolResult(StrictModel):
    evidence: list[Evidence]
    warnings: list[str]


class OperationalTools:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings
        self.retriever = Retriever(db, settings)

    async def call(self, name: str, arguments: dict) -> ToolResult:
        if name in {"search_knowledge", "search_incidents"}:
            args = KnowledgeArgs.model_validate(arguments)
            rows = await self.retriever.search(
                args.query,
                args.service,
                args.reference_time,
                args.mode,
                args.limit,
                "incident" if name == "search_incidents" else None,
            )
            evidence = self.retriever.evidence(rows, self.settings.context_chars)
            return ToolResult(
                evidence=evidence, warnings=[] if evidence else ["No matching knowledge"]
            )
        if name == "get_document_section":
            from opspilot.rag.retrieval import DEPENDENCIES

            args = SectionArgs.model_validate(arguments)
            rows = await asyncio.to_thread(
                self.db.read,
                """
                SELECT c.*,d.title,d.service,d.published_at FROM chunks c
                JOIN documents d USING(document_id,version)
                WHERE c.section_id=:section AND c.embedding_key=:key
                  AND d.service=ANY(:services) AND d.published_at<=:reference
                  AND NOT EXISTS (SELECT 1 FROM documents newer WHERE newer.document_id=d.document_id
                    AND newer.published_at>d.published_at AND newer.published_at<=:reference)
                ORDER BY c.start_line LIMIT 10""",
                {
                    "section": args.section_id,
                    "key": self.settings.embedding_key,
                    "services": DEPENDENCIES[args.service],
                    "reference": args.reference_time,
                },
            )
            evidence = self.retriever.evidence(rows, self.settings.context_chars)
            return ToolResult(
                evidence=evidence, warnings=[] if evidence else ["Section unavailable in scope"]
            )
        if name not in {"inspect_logs", "fetch_service_metrics", "list_service_changes"}:
            raise ValueError("Unsupported tool")
        args = OperationalArgs.model_validate(arguments)
        params = args.model_dump()
        datasets = await asyncio.to_thread(
            self.db.read, "SELECT * FROM datasets WHERE dataset_id=:dataset_id", params
        )
        if not datasets:
            raise ValueError("Unknown dataset")
        dataset = datasets[0]
        if args.reference_time > dataset["reference_time"]:
            raise ValueError("Reference time exceeds the synthetic dataset snapshot")
        if args.start < dataset["start_time"]:
            raise ValueError("Requested window predates dataset coverage")
        predicate = """dataset_id=:dataset_id AND service=:service AND ts>=:start
                       AND ts<:end AND available_at<=:reference_time"""
        warnings = []
        if name == "inspect_logs":
            counts = await asyncio.to_thread(
                self.db.read,
                f"SELECT code,level,count(*) AS count,min(ts) AS first_seen,max(ts) AS last_seen FROM log_events WHERE {predicate} GROUP BY code,level ORDER BY count DESC,code",
                params,
            )
            rows = await asyncio.to_thread(
                self.db.read,
                f"SELECT event_id,ts,code,level,message FROM log_events WHERE {predicate} ORDER BY ts,event_id LIMIT :limit",
                params,
            )
            total = sum(r["count"] for r in counts)
            payload = {
                "rows": rows,
                "code_counts": counts,
                "total_rows": total,
                "truncated": total > len(rows),
                "coverage": "event sample; no completeness guarantee",
            }
            kind = "logs"
        elif name == "list_service_changes":
            rows = await asyncio.to_thread(
                self.db.read,
                f"SELECT change_id,ts,description,version FROM change_events WHERE {predicate} ORDER BY ts,change_id LIMIT :limit",
                params,
            )
            total = (
                await asyncio.to_thread(
                    self.db.read,
                    f"SELECT count(*) AS n FROM change_events WHERE {predicate}",
                    params,
                )
            )[0]["n"]
            payload = {"rows": rows, "total_rows": total, "truncated": total > len(rows)}
            kind = "changes"
        else:
            params["mid"] = args.start + (args.end - args.start) / 2
            rows = await asyncio.to_thread(
                self.db.read,
                f"""
                SELECT metric,unit,CASE WHEN ts<:mid THEN 'baseline' ELSE 'current' END AS period,
                    count(*) AS sample_count, count(DISTINCT ts) AS observed_minutes,
                    avg(value) AS mean, max(value) AS max,
                    percentile_cont(0.95) WITHIN GROUP(ORDER BY value) AS p95,
                    min(ts) AS first_sample,max(ts) AS last_sample
                FROM metric_samples WHERE {predicate}
                GROUP BY metric,unit,period ORDER BY metric,period""",
                params,
            )
            payload = {
                "series": rows,
                "sample_count": sum(r["sample_count"] for r in rows),
                "period_seconds": (args.end - args.start).total_seconds() / 2,
                "definition": "p95 is computed from supplied samples; durations are sampled requests",
                "coverage": "observed_minutes/period_seconds; inspect before inferring health",
            }
            kind = "metrics"
            total = payload["sample_count"]
        if total == 0:
            warnings.append(
                f"No {kind} available for {args.service} in this window; absence does not prove health"
            )
        payload.update(
            {
                "dataset_id": args.dataset_id,
                "start": args.start.isoformat(),
                "end": args.end.isoformat(),
                "reference_time": args.reference_time.isoformat(),
            }
        )
        serialized = json.dumps(payload, default=str, sort_keys=True)
        evidence = Evidence(
            evidence_id=f"{kind}-{stable_id(name, args.service, serialized)}",
            kind=kind,
            source=f"synthetic/{args.dataset_id}/{args.service}/{name}",
            service=args.service,
            observed_at=args.end,
            captured_at=datetime.now(UTC),
            summary=f"{args.service}: {total} {kind} observations in [{args.start.isoformat()}, {args.end.isoformat()})",
            data=json.loads(serialized),
        )
        return ToolResult(evidence=[evidence], warnings=warnings)
