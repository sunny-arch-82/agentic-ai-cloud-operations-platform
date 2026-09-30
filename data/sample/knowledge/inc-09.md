---
document_id: inc-09
version: '1'
title: "Historical case 9: Retry amplification"
service: payments
kind: incident
published_at: '2026-08-01T00:00:00+00:00'
synthetic: true
---
# Historical case 9: Retry amplification
## Signals
RETRY_BURST retry amplification repeated payment attempts idempotency exponential backoff

## Interpretation
This resolved synthetic historical case predates all live fixture windows. Retry bursts can amplify upstream problems. Repeated payment attempts must preserve idempotency and respect overall time budgets. More retries may increase latency without improving success.

## Diagnostic steps
Lessons from the historical review: Compare attempts per request and PSP_TIMEOUT counts. Request retry telemetry if absent. Have an operator review backoff and idempotency configuration before considering changes.
