---
document_id: rb-slow-query
version: '1'
title: "Slow database queries"
service: postgres
kind: runbook
published_at: '2026-07-01T00:00:00+00:00'
synthetic: true
---
# Slow database queries
## Signals
SLOW_QUERY query execution duration database statement timeout plan sequential scan

## Interpretation
Slow execution after a connection is obtained differs from waiting for a connection. A high query duration with modest connection utilization suggests checking plans and locks rather than assuming pool exhaustion.

## Diagnostic steps
Inspect authorized query timing summaries and lock information. Compare execution latency with connection wait measurements. Query plans and lock details are not supplied by every OpsPilot fixture.
