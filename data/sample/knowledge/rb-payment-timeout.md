---
document_id: rb-payment-timeout
version: '1'
title: "Downstream payment timeout"
service: payments
kind: runbook
published_at: '2026-07-01T00:00:00+00:00'
synthetic: true
---
# Downstream payment timeout
## Signals
PSP_TIMEOUT DEPENDENCY_TIMEOUT payments gateway timeout upstream checkout retry deadline

## Interpretation
Payment gateway timeouts can increase checkout latency while database utilization remains normal. Correlate PSP_TIMEOUT in payments with DEPENDENCY_TIMEOUT in checkout. Distinguish the provider deadline from an internal connection queue.

## Diagnostic steps
Compare payment latency and timeout rates before and during the incident. Check provider status through an authorized operator. Inspect retry counts and total deadline; avoid recommending more retries without understanding amplification.
