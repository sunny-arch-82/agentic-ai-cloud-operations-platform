---
document_id: rb-serialization
version: '1'
title: "Checkout serialization regression"
service: checkout
kind: runbook
published_at: '2026-07-01T00:00:00+00:00'
synthetic: true
---
# Checkout serialization regression
## Signals
SERIALIZATION_ERROR checkout deployment schema response serializer validation regression version

## Interpretation
A serializer change can produce checkout errors immediately after a release. SERIALIZATION_ERROR differs from PostgreSQL transaction serialization failures. Compare release timing with first failures and unaffected dependency metrics.

## Diagnostic steps
Inspect application version and offending response shape. Compare error distribution before and after release. Ask the release owner to assess rollback; OpsPilot cannot perform rollback.
