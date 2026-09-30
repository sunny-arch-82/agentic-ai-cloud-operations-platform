---
document_id: rb-inventory
version: '1'
title: "Inventory reservation failures"
service: inventory
kind: runbook
published_at: '2026-07-01T00:00:00+00:00'
synthetic: true
---
# Inventory reservation failures
## Signals
RESERVATION_CONFLICT OUT_OF_STOCK inventory reservation checkout stock conflict failure

## Interpretation
Reservation conflicts reflect concurrent stock updates and may be business-level conflicts rather than service outages. Separate OUT_OF_STOCK responses from unexpected server failures.

## Diagnostic steps
Inspect reservation error codes, affected products, transaction duration, and dependency health. Preserve the distinction between business rejection and infrastructure failure.
