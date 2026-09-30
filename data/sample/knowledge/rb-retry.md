---
document_id: rb-retry
version: '1'
title: "Retry amplification"
service: payments
kind: runbook
published_at: '2026-07-01T00:00:00+00:00'
synthetic: true
---
# Retry amplification
## Signals
RETRY_BURST retry amplification repeated payment attempts idempotency exponential backoff

## Interpretation
Retry bursts can amplify upstream problems. Repeated payment attempts must preserve idempotency and respect overall time budgets. More retries may increase latency without improving success.

## Diagnostic steps
Compare attempts per request and PSP_TIMEOUT counts. Request retry telemetry if absent. Have an operator review backoff and idempotency configuration before considering changes.
