# Validation record

Release: OpsPilot v1.0.0-portfolio.

The owner requested that project execution, evaluations, benchmarks, database experiments, and additional tests stop before packaging. That instruction was followed. Test/evaluation source is included for later execution.

## Executed before the stop instruction

| Work | Observed result |
| --- | --- |
| `uv sync` | Dependencies installed, lock created; Python 3.12.14 |
| `uv run python -m compileall -q src` | Completed at that source snapshot |
| Ruff lint/fix and formatting | Completed during development |
| `uv run pytest -m 'not integration' -q` | 39 passed, 22 deselected |
| `uv run pytest -q` with test database URL | 61 passed, 1 warning, 5.65 seconds |
| `uv run opspilot bootstrap` | Six datasets, 241 logs, 8,700 metric samples, two changes; 24 documents/72 chunks |
| `uv run opspilot mcp-check` | Official SDK stdio session listed six schemas and read metrics |

The database run used PostgreSQL/PGlite with pgvector behind its PostgreSQL wire adapter. Tests exercised application SQL, the Alembic migration, vector/full-text queries, MCP subprocess, LangGraph, API through TestClient, and persistence. Native PostgreSQL/Docker were unavailable. Compose and CI target native PostgreSQL/pgvector, which remains to be run by the owner.

The warning was Alembic's path-separator deprecation. Test elapsed time is not a service performance benchmark.

Final source edits added an outer MCP/investigation timeout and prevented failed workflows from being labeled completed. Those edits and final packaging were not retested. **No fresh all-tests-pass claim is made for the final archive.**

## Not executed or measured

- Retrieval evaluation/Recall@K/MRR: **NOT MEASURED YET**.
- Generated-answer semantic groundedness/correctness: **NOT MEASURED YET**.
- Agent diagnosis quality or verifier benefit: **NOT MEASURED YET**.
- Throughput, latency percentiles, API cost, business impact: **NOT MEASURED YET**.
- Real OpenAI calls: **NOT EXECUTED**.
- Native Docker build/Compose launch and GitHub-hosted CI: **NOT EXECUTED**.
- AWS: **NOT DEPLOYED**; Terraform is not included.

No quality evaluation result files are supplied. Future results should identify source revision, environment, corpus, model/prompts, configuration, and sample counts.
