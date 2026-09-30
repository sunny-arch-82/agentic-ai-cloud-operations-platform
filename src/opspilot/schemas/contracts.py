"""Application-owned contracts; captured evidence cannot be authored by an LLM."""

from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Service = Literal["checkout", "payments", "inventory", "postgres"]
ToolName = Literal[
    "search_knowledge",
    "search_incidents",
    "get_document_section",
    "inspect_logs",
    "fetch_service_metrics",
    "list_service_changes",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Window(StrictModel):
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def valid(self):
        if not 0 < (self.end - self.start).total_seconds() <= 86400:
            raise ValueError("Time window must be positive and at most 24 hours")
        return self


class QueryRequest(StrictModel):
    question: str = Field(min_length=5, max_length=2000)
    service: Service = "checkout"
    reference_time: AwareDatetime
    retrieval_mode: Literal["semantic", "lexical", "hybrid"] | None = None


class InvestigationRequest(QueryRequest):
    dataset_id: str = Field(default="s01", pattern=r"^s0[1-6]$")
    time_window: Window

    @model_validator(mode="after")
    def no_future(self):
        if self.time_window.end > self.reference_time:
            raise ValueError("Time window cannot extend beyond reference_time")
        return self


class Evidence(StrictModel):
    evidence_id: str
    kind: Literal["document", "logs", "metrics", "changes"]
    source: str
    service: str
    observed_at: datetime
    captured_at: datetime
    summary: str
    data: dict[str, Any]


class Claim(StrictModel):
    statement: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(max_length=20)


class Hypothesis(Claim):
    contradictory_evidence_ids: list[str] = Field(max_length=20)
    confidence: Literal["low", "medium", "high"]
    uncertainty: str = Field(max_length=2000)


class Draft(StrictModel):
    observations: list[Claim] = Field(max_length=12)
    hypotheses: list[Hypothesis] = Field(max_length=6)
    missing_evidence: list[str] = Field(max_length=12)
    recommended_next_steps: list[Claim] = Field(max_length=10)


class ToolCall(StrictModel):
    name: ToolName
    service: Service
    query: str | None
    section_id: str | None


class InvestigatorDecision(StrictModel):
    action: Literal["gather", "draft"]
    tool_calls: list[ToolCall] = Field(max_length=4)
    draft: Draft | None
    rationale: str = Field(max_length=1000)

    @model_validator(mode="after")
    def coherent(self):
        if self.action == "gather" and (not self.tool_calls or self.draft is not None):
            raise ValueError("Gather decisions require tools and no draft")
        if self.action == "draft" and (self.draft is None or self.tool_calls):
            raise ValueError("Draft decisions require a draft and no tools")
        return self


class Verification(StrictModel):
    verdict: Literal["supported", "revise", "insufficient"]
    issues: list[str] = Field(max_length=12)
    unsupported_claims: list[str] = Field(max_length=20)
    additional_checks: list[ToolCall] = Field(max_length=2)


class AnswerDraft(StrictModel):
    status: Literal["answered", "insufficient_evidence"]
    answer: str = Field(max_length=5000)
    claims: list[Claim] = Field(max_length=12)


class Answer(AnswerDraft):
    evidence: list[Evidence]
    citations: list[str]
    mode: str
    model: str
    embedding_key: str


class ToolActivity(StrictModel):
    name: str
    service: str
    status: Literal["ok", "error", "rejected"]
    duration_ms: float
    evidence_ids: list[str]
    error: str | None = None


class InvestigationReport(StrictModel):
    investigation_id: str
    question: str
    service: Service
    dataset_id: str
    reference_time: AwareDatetime
    time_window: Window
    status: Literal["completed", "incomplete", "failed"]
    assessment: Literal["hypotheses", "insufficient_evidence"]
    observations: list[Claim]
    hypotheses: list[Hypothesis]
    evidence: list[Evidence]
    contradictory_evidence: list[str]
    missing_evidence: list[str]
    recommended_next_steps: list[Claim]
    citations: list[str]
    verification: Verification | None
    tool_activity: list[ToolActivity]
    model_calls: int
    tool_calls: int
    revisions: int
    duration_ms: float
    model: str
    mode: str
    prompt_version: str = "1.0"
    token_usage: dict[str, int]
    limitations: list[str]
