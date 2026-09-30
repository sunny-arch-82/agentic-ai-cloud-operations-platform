---
document_id: inc-05
version: '1'
title: "Historical case 5: Missing telemetry and partial evidence"
service: global
kind: incident
published_at: '2026-08-01T00:00:00+00:00'
synthetic: true
---
# Historical case 5: Missing telemetry and partial evidence
## Signals
missing telemetry absent logs metrics stale monitoring gap unknown availability insufficient evidence

## Interpretation
This resolved synthetic historical case predates all live fixture windows. An empty query may indicate collection failure, wrong service, wrong time range, or no events. Absence of error logs does not prove availability. Metric coverage must be checked before deriving health.

## Diagnostic steps
Lessons from the historical review: Validate service and UTC window, collector freshness, retention, and permissions. Report insufficient evidence explicitly. Request missing metrics or traces instead of inventing a diagnosis.
