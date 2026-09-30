---
document_id: inc-08
version: '1'
title: "Historical case 8: Slow database queries"
service: postgres
kind: incident
published_at: '2026-08-01T00:00:00+00:00'
synthetic: true
---
# Historical case 8: Slow database queries
## Signals
SLOW_QUERY query execution duration database statement timeout plan sequential scan

## Interpretation
This resolved synthetic historical case predates all live fixture windows. Slow execution after a connection is obtained differs from waiting for a connection. A high query duration with modest connection utilization suggests checking plans and locks rather than assuming pool exhaustion.

## Diagnostic steps
Lessons from the historical review: Inspect authorized query timing summaries and lock information. Compare execution latency with connection wait measurements. Query plans and lock details are not supplied by every OpsPilot fixture.
