"""Two-role LangGraph with application-owned evidence, scope and bounded control."""

import asyncio
import json
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from opspilot.core.logging import event
from opspilot.models.llm import InvalidModelOutput
from opspilot.rag.retrieval import DEPENDENCIES
from opspilot.schemas.contracts import (
    Draft,
    InvestigatorDecision,
    ToolActivity,
    Verification,
)
from opspilot.services.validation import validate_draft


class State(TypedDict, total=False):
    decision: str
    pending: list
    draft: Draft | None
    verification: Verification | None
    force_draft: bool


class BudgetExhausted(RuntimeError):
    pass


class InvestigationWorkflow:
    def __init__(self, request, settings, model, tools, investigation_id):
        self.request, self.settings, self.model, self.tools = request, settings, model, tools
        self.investigation_id = investigation_id
        self.model_calls = self.tool_calls = self.revisions = 0
        self.started = time.monotonic()
        self.evidence, self.activity, self.issues = {}, [], []
        self.failed = False
        self.last_state = {}
        self.completed_calls = set()
        graph = StateGraph(State)
        graph.add_node("investigator", self.investigator)
        graph.add_node("tools", self.collect)
        graph.add_node("verifier", self.verifier)
        graph.add_edge(START, "investigator")
        graph.add_conditional_edges(
            "investigator",
            lambda s: s["decision"],
            {"gather": "tools", "draft": "verifier", "stop": END},
        )
        graph.add_edge("tools", "investigator")
        graph.add_conditional_edges(
            "verifier",
            lambda s: s["decision"],
            {"gather": "tools", "revise": "investigator", "stop": END},
        )
        self.graph = graph.compile()

    def remaining(self):
        return self.settings.deadline_seconds - (time.monotonic() - self.started)

    def context(self):
        packed, used = [], 0
        # Telemetry is kept ahead of background knowledge; original evidence remains intact.
        for item in sorted(self.evidence.values(), key=lambda e: e.kind == "document"):
            value = item.model_dump(mode="json")
            if item.kind == "logs":
                value["data"] = dict(value["data"], rows=value["data"]["rows"][:5])
                value["data"]["model_view_rows_limited"] = True
            size = len(json.dumps(value))
            if used + size <= self.settings.context_chars:
                packed.append(value)
                used += size
        return packed

    async def generate(self, role, state, schema):
        for attempt in range(2):
            if self.model_calls >= self.settings.max_model_calls or self.remaining() <= 0:
                raise BudgetExhausted("Model-call budget or investigation deadline exhausted")
            self.model_calls += 1
            started = time.monotonic()
            payload = {
                "request": self.request.model_dump(mode="json"),
                "evidence": self.context(),
                "draft": state.get("draft").model_dump(mode="json") if state.get("draft") else None,
                "verification": state.get("verification").model_dump(mode="json")
                if state.get("verification")
                else None,
                "revisions": self.revisions,
                "force_draft": state.get("force_draft", False),
                "remaining_model_calls": self.settings.max_model_calls - self.model_calls,
                "remaining_tool_calls": self.settings.max_tool_calls - self.tool_calls,
                "completed_tools": [a.model_dump(mode="json") for a in self.activity],
                "allowed_services": DEPENDENCIES[self.request.service][:-1],
            }
            try:
                async with asyncio.timeout(
                    min(self.settings.provider_timeout_seconds, self.remaining())
                ):
                    result = await self.model.generate(role, payload, schema)
                return schema.model_validate(
                    result.model_dump() if hasattr(result, "model_dump") else result
                )
            except (InvalidModelOutput, ValidationError, ValueError):
                if attempt == 1:
                    raise InvalidModelOutput(
                        "Model output invalid after one bounded repair"
                    ) from None
            finally:
                event(
                    "model_call",
                    investigation_id=self.investigation_id,
                    role=role,
                    model=self.settings.model_id,
                    duration_ms=round((time.monotonic() - started) * 1000, 2),
                    model_call=self.model_calls,
                )

    async def investigator(self, state):
        self.last_state = state
        try:
            decision = await self.generate("investigator", state, InvestigatorDecision)
            if decision.action == "draft":
                draft, invalid = validate_draft(decision.draft, set(self.evidence))
                self.issues.extend(invalid)
                result = {"decision": "draft", "draft": draft, "pending": []}
            else:
                result = {"decision": "gather", "pending": decision.tool_calls}
        except BudgetExhausted as exc:
            self.issues.append(str(exc))
            result = {"decision": "stop"}
        except Exception as exc:
            self.failed = True
            self.issues.append(f"Investigator unavailable: {type(exc).__name__}")
            result = {"decision": "stop"}
        self.last_state = {**state, **result}
        return result

    def arguments(self, call):
        if call.service not in DEPENDENCIES[self.request.service]:
            raise ValueError("Requested service is outside investigation dependency scope")
        if call.name in {"search_knowledge", "search_incidents"}:
            return {
                "query": call.query or self.request.question,
                "service": call.service,
                "reference_time": self.request.reference_time.isoformat(),
                "mode": self.request.retrieval_mode or self.settings.retrieval_mode,
                "limit": self.settings.top_k,
            }
        if call.name == "get_document_section":
            if not call.section_id:
                raise ValueError("A section identifier is required")
            return {
                "section_id": call.section_id,
                "service": call.service,
                "reference_time": self.request.reference_time.isoformat(),
            }
        return {
            "dataset_id": self.request.dataset_id,
            "service": call.service,
            "start": self.request.time_window.start.isoformat(),
            "end": self.request.time_window.end.isoformat(),
            "reference_time": self.request.reference_time.isoformat(),
            "limit": 100,
        }

    async def collect(self, state):
        force_draft = False
        for call in state.get("pending", []):
            if self.tool_calls >= self.settings.max_tool_calls or self.remaining() <= 0:
                self.issues.append("Tool-call budget or deadline exhausted")
                force_draft = True
                break
            self.tool_calls += 1  # Attempts count, including invalid and repeated calls.
            started = time.monotonic()
            ids, error, status = [], None, "ok"
            try:
                args = self.arguments(call)
                key = json.dumps([call.name, args], sort_keys=True)
                if key in self.completed_calls:
                    raise ValueError("Identical tool call already completed")
                async with asyncio.timeout(
                    min(self.settings.tool_timeout_seconds, self.remaining())
                ):
                    result = await self.tools.call(call.name, args)
                for evidence in result.evidence:
                    if evidence.service not in DEPENDENCIES[self.request.service]:
                        raise ValueError("Tool returned out-of-scope service evidence")
                    if evidence.observed_at > self.request.reference_time:
                        raise ValueError("Tool returned future evidence")
                    self.evidence.setdefault(evidence.evidence_id, evidence)
                    ids.append(evidence.evidence_id)
                self.completed_calls.add(key)
                self.issues.extend(result.warnings)
            except ValueError:
                status, error = "rejected", "Tool validation or scope check failed"
                self.issues.append(f"{call.name}: {error}")
            except Exception as exc:
                status, error = "error", f"Tool unavailable ({type(exc).__name__})"
                self.issues.append(f"{call.name}: {error}")
            duration = round((time.monotonic() - started) * 1000, 2)
            self.activity.append(
                ToolActivity(
                    name=call.name,
                    service=call.service,
                    status=status,
                    duration_ms=duration,
                    evidence_ids=ids,
                    error=error,
                )
            )
            event(
                "tool_call",
                investigation_id=self.investigation_id,
                tool=call.name,
                service=call.service,
                status=status,
                duration_ms=duration,
            )
        result = {"pending": [], "force_draft": force_draft}
        self.last_state = {**state, **result}
        return result

    async def verifier(self, state):
        self.last_state = state
        try:
            verdict = await self.generate("verifier", state, Verification)
            if verdict.verdict == "revise" and self.revisions < self.settings.max_revisions:
                self.revisions += 1
                result = {
                    "verification": verdict,
                    "decision": "gather" if verdict.additional_checks else "revise",
                    "pending": verdict.additional_checks,
                }
            else:
                if verdict.verdict == "revise":
                    self.issues.append("Verifier revision limit reached")
                result = {"verification": verdict, "decision": "stop"}
        except BudgetExhausted as exc:
            self.issues.append(str(exc))
            result = {"decision": "stop"}
        except Exception as exc:
            self.issues.append(f"Verifier unavailable: {type(exc).__name__}")
            result = {"decision": "stop"}
        self.last_state = {**state, **result}
        return result

    async def run(self):
        try:
            async with asyncio.timeout(max(self.remaining(), 0.001)):
                state = await self.graph.ainvoke(
                    {"draft": None, "verification": None, "pending": []},
                    config={"recursion_limit": 80},
                )
                self.last_state = state
        except TimeoutError:
            self.issues.append("Investigation deadline exceeded; execution cancelled")
        except Exception as exc:
            self.failed = True
            self.issues.append(f"Workflow failed ({type(exc).__name__})")
        return self.last_state
