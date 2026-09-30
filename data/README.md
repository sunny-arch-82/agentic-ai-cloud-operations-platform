# Original synthetic fixtures

`sample/` contains fictional data generated specifically for OpsPilot, shared under the root MIT license. It contains no real employer/customer incidents or copied proprietary runbooks.

Generator: `scripts/generate_sample_data.py`; seed: `20260901`. `sample/manifest.json` records an operations-file digest. The fixture snapshot ends at `2026-09-01T12:00:00Z`. Use the supplied example window, not the current clock.

Documents have immutable versions, service/type metadata, publication dates, and synthetic markers. Operations have event and availability timestamps. Durations are sampled synthetic request observations. Percentiles are computed from those samples.

Relevance judgments and hidden scenario labels are separate under `evals/datasets`. Runtime ingestion only reads `data/sample`. Never put a current scenario's answer/postmortem into its searchable evidence and describe the result as independent diagnosis.

Seeding prevents duplicate rows but does not overwrite changed fixtures. Use an isolated fresh database when changing data until explicit data migration support is added.
