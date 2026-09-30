---
document_id: svc-inventory
version: '1'
title: "Inventory service"
service: inventory
kind: service
published_at: '2026-07-01T00:00:00+00:00'
synthetic: true
---
# Inventory service
## Signals
inventory ownership dependencies latency errors service boundaries

## Interpretation
The synthetic inventory service depends on postgres for reservation storage. Sample telemetry is scoped by dataset and UTC timestamps. Reference time represents the observation cutoff.

## Diagnostic steps
Use service-filtered evidence. A dependency symptom does not automatically establish the affected application's root cause.
