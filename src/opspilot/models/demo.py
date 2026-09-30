"""Transparent offline simulator. Rules consume captured evidence, never scenario labels.

This exercises orchestration/contracts; it does not measure LLM reasoning or groundedness.
"""

import re

from opspilot.schemas.contracts import (
    AnswerDraft,
    Claim,
    Draft,
    Hypothesis,
    InvestigatorDecision,
    ToolCall,
    Verification,
)


def call(name, service, query=None):
    return ToolCall(name=name, service=service, query=query, section_id=None)


def metric(evidence, service, metric_name, period="current"):
    for e in evidence:
        if e["kind"] == "metrics" and e["service"] == service:
            for row in e["data"]["series"]:
                if row["metric"] == metric_name and row["period"] == period:
                    return row, e["evidence_id"]
    return None, None


def seen(evidence, kind, service):
    return any(e["kind"] == kind and e["service"] == service for e in evidence)


def codes(evidence, service):
    return {
        row["code"]
        for e in evidence
        if e["kind"] == "logs" and e["service"] == service
        for row in e["data"]["code_counts"]
        if row["level"] == "ERROR"
    }


class DemoModel:
    def __init__(self):
        self.usage = {"input_tokens": 0, "output_tokens": 0}

    async def generate(self, role, payload, schema):
        result = {"investigator": self.investigate, "verifier": self.verify, "answer": self.answer}[
            role
        ](payload)
        return schema.model_validate(result.model_dump())

    def investigate(self, payload):
        evidence = payload["evidence"]
        service = payload["request"]["service"]
        if not evidence:
            return InvestigatorDecision(
                action="gather",
                draft=None,
                rationale="Inspect the scoped service and its runbooks.",
                tool_calls=[
                    call("inspect_logs", service),
                    call("fetch_service_metrics", service),
                    call("list_service_changes", service),
                    call("search_knowledge", service, payload["request"]["question"]),
                ],
            )
        err = codes(evidence, service)
        extra = []
        if "DB_POOL_TIMEOUT" in err and not seen(evidence, "metrics", "postgres"):
            extra = [
                call("fetch_service_metrics", "postgres"),
                call("search_knowledge", service, "DB_POOL_TIMEOUT connection pool exhaustion"),
            ]
        elif err & {"DEPENDENCY_TIMEOUT", "PSP_TIMEOUT"} and not seen(
            evidence, "metrics", "payments"
        ):
            extra = [
                call("fetch_service_metrics", "payments"),
                call("inspect_logs", "payments"),
                call("search_knowledge", service, "PSP_TIMEOUT downstream payment timeout"),
            ]
        elif "SERIALIZATION_ERROR" in err and not seen(evidence, "metrics", "postgres"):
            extra = [
                call("fetch_service_metrics", "postgres"),
                call(
                    "search_knowledge",
                    service,
                    "SERIALIZATION_ERROR response serializer regression",
                ),
            ]
        if extra and not payload.get("force_draft"):
            return InvestigatorDecision(
                action="gather",
                draft=None,
                rationale="Check the dependency indicated by observed errors.",
                tool_calls=extra,
            )
        return InvestigatorDecision(
            action="draft",
            tool_calls=[],
            draft=self.draft(payload),
            rationale="Summarize observed signals with qualified hypotheses.",
        )

    def draft(self, payload):
        evidence = payload["evidence"]
        service = payload["request"]["service"]
        observations, hypotheses, missing, steps = [], [], [], []
        err = codes(evidence, service)
        ids = {
            e["kind"]: e["evidence_id"]
            for e in evidence
            if e["service"] == service and e["kind"] != "document"
        }
        for e in evidence:
            if e["kind"] == "metrics":
                for row in e["data"]["series"]:
                    if row["period"] == "current":
                        value = (
                            row["p95"] if row["metric"] == "request_duration_ms" else row["mean"]
                        )
                        statistic = (
                            "sample p95"
                            if row["metric"] == "request_duration_ms"
                            else "sample mean"
                        )
                        observations.append(
                            Claim(
                                statement=f"{e['service']} {row['metric']} {statistic} is {value:.2f} {row['unit']} from {row['sample_count']} samples.",
                                evidence_ids=[e["evidence_id"]],
                            )
                        )
            if e["kind"] == "logs" and e["service"] == service:
                for row in e["data"]["code_counts"]:
                    if row["level"] == "ERROR":
                        observations.append(
                            Claim(
                                statement=f"{row['code']} appears {row['count']} times; first observed at {row['first_seen']}.",
                                evidence_ids=[e["evidence_id"]],
                            )
                        )
        db, db_id = metric(evidence, "postgres", "connection_utilization_pct")
        pay, pay_id = metric(evidence, "payments", "request_duration_ms")
        lat, lat_id = metric(evidence, service, "request_duration_ms")
        errors, _ = metric(evidence, service, "error_rate_pct")
        traffic, traffic_id = metric(evidence, service, "request_rate_rps")
        contradictions = []
        if pay and pay["p95"] < 400:
            contradictions.append(pay_id)
        if "DB_POOL_TIMEOUT" in err and db and db["mean"] > 90:
            hypotheses.append(
                Hypothesis(
                    statement="Database connection exhaustion is a likely contributor to checkout delays.",
                    evidence_ids=[ids["logs"], db_id],
                    contradictory_evidence_ids=[],
                    confidence="medium",
                    uncertainty="Pool waits and high utilization align; transaction/connection-owner evidence is still missing.",
                )
            )
            missing.append(
                "Connection ownership and long transaction measurements are unavailable."
            )
            steps.append(
                Claim(
                    statement="Ask an operator to inspect connection holders and long-running transactions.",
                    evidence_ids=[db_id],
                )
            )
        elif err & {"DEPENDENCY_TIMEOUT", "PSP_TIMEOUT"} and pay and pay["p95"] > 1000:
            hypotheses.append(
                Hypothesis(
                    statement="Downstream payment timeout is a likely contributor to checkout latency.",
                    evidence_ids=[ids["logs"], pay_id],
                    contradictory_evidence_ids=[],
                    confidence="medium",
                    uncertainty="Provider traces and retry counts are required to establish the underlying mechanism.",
                )
            )
            missing.append("External gateway status and distributed traces are unavailable.")
            steps.append(
                Claim(
                    statement="Review gateway deadlines and retry counts with the payments owner.",
                    evidence_ids=[pay_id],
                )
            )
        elif "SERIALIZATION_ERROR" in err:
            hypotheses.append(
                Hypothesis(
                    statement="A checkout deployment serialization regression is plausible.",
                    evidence_ids=[ids["logs"]] + ([ids["changes"]] if ids.get("changes") else []),
                    contradictory_evidence_ids=contradictions,
                    confidence="medium",
                    uncertainty="Timing and serializer errors support investigation; a reproducer or controlled rollback is not available.",
                )
            )
            steps.append(
                Claim(
                    statement="Inspect the response shape introduced by the release and reproduce serializer failures.",
                    evidence_ids=[ids["logs"]],
                )
            )
        elif (
            lat
            and traffic
            and errors
            and lat["p95"] < 400
            and errors["mean"] < 1
            and traffic["mean"] > 200
        ):
            hypotheses.append(
                Hypothesis(
                    statement="The sampled signals are consistent with a benign traffic increase.",
                    evidence_ids=[lat_id, traffic_id],
                    contradictory_evidence_ids=[],
                    confidence="medium",
                    uncertainty="This is a sampled observation window, not a guarantee of full production health.",
                )
            )
            steps.append(
                Claim(
                    statement="Continue checking latency, errors, and saturation as traffic evolves.",
                    evidence_ids=[lat_id],
                )
            )
        if not hypotheses:
            missing.append(
                "Available telemetry does not support a specific operational explanation."
            )
            steps.append(
                Claim(
                    statement="Verify the service, time window, collector freshness, and access before diagnosing.",
                    evidence_ids=list(ids.values())[:2],
                )
            )
        # A deployment after the first observed error is explicit contradictory evidence.
        first_errors = [
            r["first_seen"]
            for e in evidence
            if e["kind"] == "logs" and e["service"] == service
            for r in e["data"]["code_counts"]
            if r["level"] == "ERROR"
        ]
        for e in evidence:
            if e["kind"] == "changes" and e["service"] == service:
                for change in e["data"]["rows"]:
                    if first_errors and change["ts"] > min(first_errors):
                        observations.append(
                            Claim(
                                statement="The recorded deployment occurred after the first sampled errors and cannot explain their initial onset.",
                                evidence_ids=[e["evidence_id"], ids["logs"]],
                            )
                        )
                        hypotheses.append(
                            Hypothesis(
                                statement="The recorded deployment is a weak explanation for the initial onset.",
                                evidence_ids=[e["evidence_id"]],
                                contradictory_evidence_ids=[ids["logs"]],
                                confidence="low",
                                uncertainty="The deployment may affect later behavior; it happened after degradation was observed.",
                            )
                        )
        return Draft(
            observations=observations[:12],
            hypotheses=hypotheses,
            missing_evidence=missing,
            recommended_next_steps=steps,
        )

    def verify(self, payload):
        draft = Draft.model_validate(payload["draft"])
        evidence = payload["evidence"]
        if not draft.hypotheses:
            return Verification(
                verdict="insufficient",
                issues=["No sufficiently supported operational hypothesis."],
                unsupported_claims=[],
                additional_checks=[],
            )
        # A real cross-check of an alternative dependency, selected from collected evidence.
        service = payload["request"]["service"]
        if (
            service == "checkout"
            and not seen(evidence, "metrics", "payments")
            and payload["revisions"] == 0
        ):
            return Verification(
                verdict="revise",
                issues=["Check payment latency as an alternative explanation."],
                unsupported_claims=[],
                additional_checks=[call("fetch_service_metrics", "payments")],
            )
        return Verification(
            verdict="supported",
            issues=["Qualified hypotheses, not proven causes."],
            unsupported_claims=[],
            additional_checks=[],
        )

    def answer(self, payload):
        question = payload["question"].lower()
        tokens = set(re.findall(r"[a-z0-9_]+", question)) - {
            "what",
            "which",
            "how",
            "the",
            "is",
            "a",
            "to",
            "we",
            "should",
            "investigate",
        }
        selected = []
        for e in payload["evidence"]:
            doc_tokens = set(re.findall(r"[a-z0-9_]+", e["data"]["text"].lower()))
            if len(tokens & doc_tokens) / max(len(tokens), 1) >= 0.45:
                selected.append(e)
        if not selected:
            return AnswerDraft(
                status="insufficient_evidence",
                answer="The retrieved knowledge does not answer this question.",
                claims=[],
            )
        claims = [
            Claim(statement=e["data"]["text"], evidence_ids=[e["evidence_id"]])
            for e in selected[:2]
        ]
        return AnswerDraft(
            status="answered", answer="\n\n".join(c.statement for c in claims), claims=claims
        )
