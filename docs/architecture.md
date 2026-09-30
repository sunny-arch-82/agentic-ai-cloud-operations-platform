# Architecture and contracts

## Execution and state

FastAPI awaits investigation execution. The initial database record and final report are separate transactions. No durable queue, lease, resume worker, or exactly-once guarantee exists. A crash can leave an interrupted `running` record.

The investigator chooses tools and drafts hypotheses. The verifier separately reviews support/contradictions and can request bounded checks. Routing, SQL, aggregation, evidence IDs, schema checks, and budgets are deterministic functions, not extra agents.

| State | Owner |
| --- | --- |
| Service, dataset, reference time/window | Validated request/application |
| Tool names and schemas | Application/MCP server |
| Budgets and deadline | Workflow controller |
| Original evidence | Tool dispatcher |
| Draft claims | Investigator |
| Verdict, unsupported statements, cross-check requests | Verifier |
| Citation resolution and report status | Application |

The model gets a bounded evidence view. Log rows can be reduced in that view while code counts and the complete bounded tool result are retained. Original evidence is never overwritten by model output. The verifier receives the structured draft and evidence, not an unrestricted agent conversation.

## Scope and provenance

Operational arguments derive time/dataset from the request. Dependency scope is code-owned. Standalone MCP clients are trusted local operators; no remote authorization layer is included. MCP read-only annotations describe intent; typed functions, bound SQL, limits, and read-only transactions enforce it.

Documents have immutable versions and publication timestamps. A materialized filtered vector candidate set prevents comparison across embedding profiles. Operational reads apply event-window and availability-time filters. Metric p95 comes from supplied samples. Baseline/current periods are equal halves of the requested window.

`investigations`, `evidence_items`, and `tool_activity` preserve outputs and evidence. Evidence IDs hash tool/service/source payload; capture time does not alter source identity. A resolving ID does not prove semantic support.

## Failure behavior

Invalid inputs are rejected. Failed/rejected tools consume budget. Invalid model output gets one bounded investigation repair. Unverified hypotheses and explicitly unsupported statements are excluded from finalized conclusions. Available observations/evidence can accompany incomplete results.

The deadline includes MCP startup and graph execution. Database startup/final persistence have separate behavior. There is no production fault-tolerance or performance claim. Provider/retrieval/tool modules are replaceable boundaries, but replacement still requires compatibility and evaluation work.
