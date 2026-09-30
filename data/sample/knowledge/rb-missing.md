---
document_id: rb-missing
version: '1'
title: "Missing telemetry and partial evidence"
service: global
kind: runbook
published_at: '2026-07-01T00:00:00+00:00'
synthetic: true
---
# Missing telemetry and partial evidence
## Signals
missing telemetry absent logs metrics stale monitoring gap unknown availability insufficient evidence

## Interpretation
An empty query may indicate collection failure, wrong service, wrong time range, or no events. Absence of error logs does not prove availability. Metric coverage must be checked before deriving health.

## Diagnostic steps
Validate service and UTC window, collector freshness, retention, and permissions. Report insufficient evidence explicitly. Request missing metrics or traces instead of inventing a diagnosis.
