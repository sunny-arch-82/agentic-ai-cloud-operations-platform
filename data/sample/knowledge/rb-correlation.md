---
document_id: rb-correlation
version: '1'
title: "Deployment correlation and causal uncertainty"
service: global
kind: runbook
published_at: '2026-07-01T00:00:00+00:00'
synthetic: true
---
# Deployment correlation and causal uncertainty
## Signals
deployment correlation misleading change occurred after onset timeline causation temporal ordering

## Interpretation
A release near an incident is only a candidate explanation. A change occurring after the first observed degradation cannot explain its initial onset. Shared timing without a mechanism is weak evidence.

## Diagnostic steps
Build the symptom timeline and compare deployment timestamps. Seek mechanism-specific errors, control services, and contradictory data. Keep alternative hypotheses until evidence discriminates them.
