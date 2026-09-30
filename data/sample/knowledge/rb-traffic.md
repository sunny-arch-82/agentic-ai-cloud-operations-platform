---
document_id: rb-traffic
version: '1'
title: "Benign traffic increase"
service: checkout
kind: runbook
published_at: '2026-07-01T00:00:00+00:00'
synthetic: true
---
# Benign traffic increase
## Signals
TRAFFIC_GROWTH request_rate_rps increased traffic stable latency error budget healthy

## Interpretation
Higher request volume alone does not establish an incident. If latency, errors, and dependency utilization remain stable, a traffic increase may be benign. Missing telemetry is not evidence of healthy operation.

## Diagnostic steps
Compare request rate with latency, error percentage, and saturation in identical windows. Report healthy sampled signals with their coverage; continue monitoring rather than asserting a root cause.
