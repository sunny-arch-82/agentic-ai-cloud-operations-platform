# OpsPilot

**Agentic AI Operations & Knowledge Platform · v1.0.0.**

Investigate operational incidents with runbooks, historical incidents, logs, metrics, and deployment records. OpsPilot gathers evidence through typed MCP tools, coordinates an investigator and verifier with LangGraph, and returns structured reports with resolvable citations.

> **Status:** Complete local project source with an offline demonstration mode and a real OpenAI adapter. Real-model quality and native Docker/AWS execution remain unvalidated. Further execution was stopped at the owner's request before packaging. See [validation notes](docs/validation.md).

## Overview

OpsPilot helps an on-call engineer investigate one service and time window. It separates observations, qualified hypotheses, contradictory evidence, missing evidence, and recommended diagnostic checks. It cannot change operational infrastructure.

Quick start, without a model API key:

```bash
unzip OpsPilot-v1.0.0-portfolio.zip
cd OpsPilot
cp .env.example .env
docker compose up --build -d
```

Open **http://localhost:8000/docs**. On first launch, bootstrap runs migrations, seeds synthetic records, and indexes knowledge. The API starts after bootstrap completes. Initial downloads/builds can take several minutes.

```bash
curl -sS http://localhost:8000/ready
curl -sS -X POST http://localhost:8000/investigations \
  -H 'Content-Type: application/json' \
  --data @docs/examples/investigation-request.json
```

## Real-world problem

Checkout latency investigation requires connecting runbooks, concrete log errors, measured signals, and change timing. These sources can disagree or be incomplete. OpsPilot assembles a reviewable report without treating temporal correlation as proof of causality. Intended users are on-call backend engineers, SREs, platform engineers, and engineers learning an unfamiliar service.

## Key capabilities

**IMPLEMENTED:** Versioned synthetic knowledge ingestion; section-aware Markdown parsing; stable citations; pgvector, full-text, and hybrid retrieval; two LangGraph roles; six official-SDK MCP tools; API and report persistence; bounded execution; structured logs; test/evaluation code; Docker/Compose; GitHub CI.

**MEASURED BEFORE EXECUTION STOPPED:** Dependencies installed; source lint/compilation and unit/integration checks were performed. The last full test run reported **61 passed, 1 warning** on a PostgreSQL/PGlite runtime with pgvector. This was not native Docker validation, and final packaging edits were not retested.

**PLANNED:** Real integrations, independently reviewed evaluation labels, measured model comparisons, authentication, durable recovery, AWS deployment, larger data, and optional Python UI.

No retrieval quality, LLM quality, throughput, cost, or cloud deployment result is claimed.

## Architecture

One Python application contains the API, workflow, retrieval, provider adapters, and tool client. An MCP subprocess exposes operational reads. PostgreSQL stores knowledge, operational fixtures, reports, captured evidence, and tool activity. Only OpenAI mode needs an external model provider.

### Mermaid architecture diagram

```mermaid
flowchart TD
    API["FastAPI"] --> Graph["LangGraph control"]
    Graph --> Investigator["Investigator"]
    Investigator --> Verifier["Verifier"]
    Verifier -->|"Bounded revision"| Investigator
    Investigator --> Client["MCP client"]
    Verifier --> Client
    Client --> Server["Read-only MCP server"]
    Server --> DB["PostgreSQL and pgvector"]
    Verifier --> Checks["Citation and output checks"]
    Checks --> Report["Persisted report"]
```

See [architecture notes](docs/architecture.md) for state ownership and failure behavior.

## Agent workflow

1. The investigator chooses useful typed evidence reads.
2. Deterministic dispatch enforces the tool name, dependency scope, server-owned time window, and budgets.
3. Captured tool results become immutable evidence for the investigation.
4. The investigator drafts observations and qualified hypotheses with evidence IDs.
5. The verifier reviews support and contradictions and may request up to two additional checks within the global budget.
6. LangGraph permits the configured revision count, then stops.
7. The application removes invalid citations and explicitly flagged unsupported claims, suppresses unverified hypotheses, and saves the report.

OpenAI mode uses schema-constrained **action decisions** followed by application-dispatched MCP calls. It does not expose an unrestricted execution agent or model-generated SQL. Both roles use the selected model with distinct instructions and structured state.

Demo mode uses transparent evidence-driven rules to exercise the same graph. It does not establish general LLM reasoning or diagnostic quality and does not read hidden scenario labels.

Defaults: eight model calls, twelve tool attempts, one revision, a 90-second investigation deadline, 25-second provider timeout, and 15-second tool timeout. A malformed investigation model response gets at most one repair attempt, counted against the model budget. Failed/rejected tools count toward the tool budget.

## RAG architecture

Documents have YAML metadata, immutable versions, publication timestamps, and service/type scope. Parsing preserves sections and source line references. Chunking targets approximately 400 words with limited line overlap; oversized single lines can exceed the target. Headings inside fenced code do not create sections.

Embeddings carry a provider/model/dimension profile key. Changing that profile requires re-ingestion; unchanged fully indexed documents avoid repeat embedding calls. Changed document content needs a new version and later publication timestamp.

| Mode | Implementation |
| --- | --- |
| `semantic` | Exact pgvector cosine search; real semantic embeddings require OpenAI mode |
| `lexical` | PostgreSQL `websearch_to_tsquery` and `ts_rank_cd`; **not BM25** |
| `hybrid` | Reciprocal-rank fusion of vector and lexical candidates |

Retrieval filters service/dependencies and publication time, choosing the newest version available at the reference time. Context construction preserves complete cited chunks within a character budget. No reranker, approximate index, or query rewrite is included.

The offline embedding implementation is normalized lexical feature hashing, not a trained semantic model. Citation validity means an ID resolves to supplied evidence; semantic support still requires evaluation.

## MCP architecture

The app starts `python -m opspilot.mcp.server` in its Python environment and communicates over stdio. The official `mcp` package advertises input/output schemas. Configuration is explicitly forwarded and server logs use stderr.

| Tool | Purpose |
| --- | --- |
| `search_knowledge` | Search knowledge within service/publication scope |
| `search_incidents` | Search historical incidents only |
| `get_document_section` | Read an available original section |
| `inspect_logs` | Bounded rows plus full-window error-code counts |
| `fetch_service_metrics` | Baseline/current sample summaries with units and coverage |
| `list_service_changes` | Bounded deployment/configuration records |

Duration p95 is calculated from samples, not averaged p95 values. Empty telemetry is explicit; logs disclose truncation. The server exposes no shell, arbitrary SQL, or infrastructure actions.

Standalone diagnostic client:

```bash
uv run opspilot mcp-check
```

It lists schemas and invokes metrics over a real MCP session. Another local MCP client can use absolute command `/path/to/OpsPilot/.venv/bin/python`, arguments `-m opspilot.mcp.server`, working directory `/path/to/OpsPilot`, and the same environment. No remote HTTP MCP endpoint is included.

## Technology stack

| Technology | Role |
| --- | --- |
| Python 3.12, uv | Project-local runtime and locked dependencies |
| FastAPI, Pydantic | HTTP API, contracts, validation, OpenAPI |
| LangGraph | State, conditional tool use, bounded verification |
| Official MCP SDK | Reusable typed tool boundary |
| PostgreSQL, pgvector | Persistence, lexical/vector retrieval |
| SQLAlchemy Core, psycopg, Alembic | Parameterized SQL, transactions, migrations |
| OpenAI SDK | Real structured generation and embeddings |
| pytest, HTTPX, Ruff | Tests, API testing, static checks |
| Docker, Compose | Reproducible local app/database environment |

No Redis, Kafka, Spark, Airflow, Kubernetes, Celery, or separate vector database is required.

## Repository structure

| Path | Contents |
| --- | --- |
| `src/opspilot/api/` | FastAPI routes |
| `src/opspilot/agents/`, `workflows/` | Role prompts and LangGraph control |
| `src/opspilot/rag/` | Parsing, ingestion, retrieval |
| `src/opspilot/tools/`, `mcp/` | Read-only functions and MCP transport |
| `src/opspilot/models/` | Real provider and explicit demo implementations |
| `src/opspilot/services/` | Query/investigation orchestration and citation checks |
| `src/opspilot/storage/`, `schemas/`, `core/` | SQL, contracts, settings, JSON logs |
| `src/opspilot/evaluation.py` | Evaluation runners |
| `migrations/` | Alembic revision |
| `data/sample/` | Original synthetic fixtures |
| `evals/datasets/` | Relevance labels and separate scenario answers |
| `tests/` | Unit, workflow, API, database, MCP tests |
| `scripts/` | Deterministic fixture generator |
| `docs/` | Architecture, setup details, examples, validation, licensing |
| `.github/workflows/ci.yml` | Real lint/test/evaluation-smoke workflow |

## Synthetic dataset/scenarios

Seed `20260901` creates 24 knowledge documents, 72 chunks, six observation windows, 241 logs, 8,700 metric samples, two changes, and 40 authored knowledge questions.

| Dataset | Demonstration |
| --- | --- |
| `s01` | Database connection exhaustion signals |
| `s02` | Downstream payment timeout |
| `s03` | Checkout serializer regression after a release |
| `s04` | Higher traffic with stable sampled latency/errors |
| `s05` | Missing telemetry and an incomplete conclusion |
| `s06` | Deployment after symptom onset, contradicting an initial-cause claim |

All windows are **2026-09-01 11:00:00Z to 12:00:00Z**, with reference time **12:00:00Z**. Ranges include the start and exclude the end. Records have availability timestamps. Use fixture time, not the current wall clock.

The runtime reads only `data/sample`; hidden answers are in `evals/datasets`. Historical incidents predate current windows. These are original fictional records and authored labels, not an independently reviewed production benchmark. See [data provenance](data/README.md).

## Prerequisites

Docker Engine with the Compose plugin, internet for initial downloads, and available ports 5432/8000. No host PostgreSQL installation is required. Python development also uses Python 3.12, uv, Git, and optionally VS Code/GitHub CLI. Only real-model mode requires an OpenAI API key.

## Debian setup

Keep your existing Docker installation if present. Otherwise follow https://docs.docker.com/engine/install/debian/ and include the Compose plugin.

Install uv in an isolated tool environment:

```bash
sudo apt-get update
sudo apt-get install -y git curl unzip python3-venv pipx
pipx install uv==0.12.18
pipx ensurepath
```

Open a new terminal, then:

```bash
cd OpsPilot
uv python install 3.12
uv sync --frozen
cp .env.example .env             # first setup only
docker compose up -d db
uv run opspilot bootstrap
```

Do not overwrite an already configured `.env`. Project packages install into `.venv`, not Debian's global Python. The sample password is for a localhost synthetic demo; change `POSTGRES_PASSWORD` and the password in `OPSPILOT_DATABASE_URL` together. Use a URL-safe password or encode it in the URL. Compose overrides the host to `db`; host Python uses `localhost`.

## VS Code setup

```bash
cd OpsPilot
code .
```

Select `.venv/bin/python` using **Python: Select Interpreter**. All documented commands run from the repository root so configuration, migrations, and data paths resolve correctly.

## Environment variables

| Variable | Default/example | Purpose |
| --- | --- | --- |
| `OPSPILOT_MODE` | `demo` | `demo` or `openai` |
| `POSTGRES_PASSWORD` | Local demo value | Compose database credential |
| `OPSPILOT_DATABASE_URL` | URL in `.env.example` | Host application connection |
| `OPENAI_API_KEY` | Empty | Required in OpenAI mode |
| `OPSPILOT_LLM_MODEL` | `gpt-4.1-mini` | Structured generation |
| `OPSPILOT_EMBEDDING_MODEL` | `text-embedding-3-small` | Real embeddings |
| `OPSPILOT_EMBEDDING_DIMENSIONS` | `512` | Vector dimension/profile |
| `OPSPILOT_RETRIEVAL_MODE` | `hybrid` | Retrieval strategy |
| `OPSPILOT_TOP_K` | `5` | Context retrieval size |
| `OPSPILOT_MAX_MODEL_CALLS` | `8` | Investigation model attempts |
| `OPSPILOT_MAX_TOOL_CALLS` | `12` | Investigation tool attempts |
| `OPSPILOT_MAX_REVISIONS` | `1` | Verifier revision limit |
| `OPSPILOT_DEADLINE_SECONDS` | `90` | Investigation/model-work deadline |
| `OPSPILOT_PROVIDER_TIMEOUT_SECONDS` | `25` | Model/embedding timeout |
| `OPSPILOT_TOOL_TIMEOUT_SECONDS` | `15` | Tool timeout |
| `OPSPILOT_CONTEXT_CHARS` | `24000` | Evidence context bound |
| `OPSPILOT_LOG_LEVEL` | `INFO` | Log level |
| `OPSPILOT_DATA_DIR` | `data/sample` | Fixture directory |

Tests additionally accept `OPSPILOT_TEST_DATABASE_URL` for an isolated database.

### Configure real model operation

Edit `.env` locally:

```dotenv
OPSPILOT_MODE=openai
OPENAI_API_KEY=your-own-key-here
OPSPILOT_LLM_MODEL=gpt-4.1-mini
OPSPILOT_EMBEDDING_MODEL=text-embedding-3-small
```

The placeholder is not a credential. Do not commit a populated `.env`. Then, for host Python:

```bash
uv run opspilot bootstrap --allow-paid
uv run uvicorn opspilot.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Or recreate Docker services after changing mode:

```bash
docker compose up --build -d --force-recreate bootstrap api
```

**OpenAI mode makes paid embedding/model calls.** Compose bootstrap includes `--allow-paid`; the default demo mode makes no paid calls. CLI demo/evaluation runs in OpenAI mode also require `--allow-paid`. Per-request call limits are not a monthly billing cap. Real API calls were not executed during delivery. See [provider notes](docs/providers.md).

## Running locally

Choose all-Docker or host Python plus a Docker database. Do not bind two API instances to the same port.

### Docker workflow

```bash
docker compose up --build -d
docker compose logs -f bootstrap api
docker compose down             # stops containers; keeps the named database volume
```

Deleting the volume destroys local data; it is not needed for ordinary restarts. Changing `.env` does not change the password already stored in an existing database volume.

### Database migrations

```bash
uv run alembic upgrade head
```

Bootstrap runs this automatically. API requests never create or migrate tables. See [development notes](docs/development.md).

### Ingesting data

```bash
uv run opspilot bootstrap        # migrations + operational seed + knowledge
uv run opspilot ingest           # knowledge only
```

Add `--allow-paid` in OpenAI mode. Fixtures are included; regenerate them intentionally with `uv run python scripts/generate_sample_data.py`. Seeding prevents duplicates but does not overwrite changed existing operational records; use a fresh development database or explicit data migration for changed fixtures.

### Starting the API

```bash
uv run uvicorn opspilot.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Use `--reload` only in development. `/docs` exposes Swagger and `/openapi.json` exposes schemas. `/health` checks process liveness; `/ready` checks database/schema and the matching embedding index, not paid provider access.

### Starting a UI

Swagger and the CLI are the implemented interfaces. No separate Streamlit/Gradio application or JavaScript frontend is included.

## Example API requests

```bash
curl -sS -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' --data @docs/examples/query-request.json

curl -sS -X POST http://localhost:8000/investigations \
  -H 'Content-Type: application/json' --data @docs/examples/investigation-request.json

curl -sS http://localhost:8000/investigations/REPLACE_WITH_RETURNED_UUID
```

Investigation creation waits synchronously and returns `201` with a persisted report. Inspect its `status`: `completed`, `incomplete`, or `failed`. It never returns `202` with an implied durability guarantee. Invalid input returns `422`, missing IDs return `404`, and dependency failures can return `503`. Responses contain `X-Request-ID`.

## Example investigation

Generate a report without starting the API:

```bash
uv run opspilot demo --scenario s01 --output evals/local-results/s01-report.json
uv run opspilot demo --scenario s05 --output evals/local-results/missing-telemetry.json
uv run opspilot demo --scenario s06 --output evals/local-results/contradictory-timing.json
```

Reports include observations, hypotheses, evidence, contradictions, missing information, next steps, verification, tool activity, call counts, timing, and mode labels. The missing-data case is designed to remain incomplete. The timing case distinguishes first errors from a later deployment. These are fixture behaviors, not benchmark accuracy claims. Confidence labels are qualitative, not calibrated probabilities.

## Running tests

Test/evaluation source is provided for later execution. Extracting the ZIP runs nothing automatically.

```bash
uv sync --frozen
uv run pytest -m 'not integration' -q
```

For integration tests, create a separate disposable database once:

```bash
docker compose up -d db
docker compose exec db createdb -U opspilot opspilot_test
export OPSPILOT_TEST_DATABASE_URL='postgresql+psycopg://opspilot:local-demo-only-change-me@localhost:5432/opspilot_test'
uv run pytest -q
```

Update the password if configured differently. Omit `createdb` if the test database exists. Tests initialize schema/fixtures; never point them at a production database. Without the test URL, integration tests are skipped explicitly. Tests use demo/fake model paths, not paid calls.

```bash
uv run ruff check .
uv run ruff format --check .
```

Tests cover parsing, IDs, configuration, filters, vector/hybrid queries, idempotency, MCP calls, API behavior, budgets, revision limits, provider/malformed-output failures, missing/contradictory evidence, and policy around instruction-like log text. They do not establish real-model prompt-injection immunity.

## Running evaluations

These commands are for later use; the evaluation runners were not executed for delivery:

```bash
uv run opspilot eval --kind retrieval --split test --output evals/local-results/retrieval.json
uv run opspilot eval --kind answers --split test --output evals/local-results/answers.json
uv run opspilot eval --kind investigations --output evals/local-results/investigations.json
```

Add `--allow-paid` in OpenAI mode and ingest the real embedding profile first. Retrieval measures Recall@5/MRR@5 over distinct sections; negative questions are excluded from retrieval denominators. Answer evaluation measures schema/reference validity and abstention, not semantic faithfulness. Investigation evaluation records evidence and labels for manual review. See [evaluation methodology](evals/README.md).

## Evaluation results actually measured

| Measurement | Status |
| --- | --- |
| Recall@5 / MRR@5 / retrieval improvements | **NOT MEASURED YET** |
| Answer groundedness/correctness | **NOT MEASURED YET** |
| Investigation quality / verifier benefit | **NOT MEASURED YET** |
| p50/p95 latency / throughput / API cost | **NOT MEASURED YET** |
| Real provider calls | **NOT EXECUTED** |
| AWS | **NOT DEPLOYED** |

Do not invent accuracy, latency, savings, or business-impact resume claims. Describe implemented features and the precise scope of tests actually run.

## Known limitations

- Offline rules and hashing vectors are not real LLM/semantic-model quality. The real adapter requires your configuration and validation.
- Native Docker startup and GitHub-hosted CI were not executed here.
- Synthetic cases are small, templated, and not independently reviewed.
- Long questions can produce overly strict full-text matches under current web-search query semantics.
- There is no checkpoint/resume worker. A crash may leave a `running` record; GET explains it may have been interrupted. Retry as a new request after recovery.
- The deadline bounds MCP startup and graph execution, not database startup/final persistence. Database operations have separate timeout behavior.
- Each investigation starts an MCP subprocess; concurrency/load performance is unmeasured.
- No public authentication, multitenancy, remote MCP authorization, production RBAC, or monthly spending cap.
- Operational reads use read-only transactions, but the app credential also writes reports. A production deployment should separate database roles.
- Chunking is Markdown-oriented with approximate word budgets; no PDF/OCR pipeline.
- Valid references do not establish semantic truth. Provider/model changes require compatibility review, evaluation, and sometimes re-indexing.

## Security boundaries

Tools cannot execute infrastructure changes. The model cannot supply arbitrary SQL, shells, hosts, or time windows. Arguments are typed, SQL values are bound, reads are bounded, and cited IDs must exist. Retrieved documents/logs remain untrusted data.

Compose binds ports to localhost. Keep this release local until authentication, deployment-specific access control, and network hardening are added. Secrets belong in environment configuration, never source control or image build context. Do not ingest private operational material into a hosted provider without authorization.

## Git workflow

After reviewing/configuring the extracted repository:

```bash
git init
git add .
git commit -m "feat: release OpsPilot portfolio version"
git branch -M main
gh auth login
gh repo create opspilot --public --source=. --remote=origin --push
git checkout -b develop
git push -u origin develop
git checkout main
git tag -a v1.0.0-portfolio -m "OpsPilot portfolio release"
git push origin v1.0.0-portfolio
```

If you create an empty repository on the GitHub website, replace `gh repo create` with:

```bash
git remote add origin https://github.com/YOUR_USERNAME/opspilot.git
git push -u origin main
```

Create that remote without an initial README/license, then continue with `develop` and tagging. For later changes:

```bash
git checkout develop
git checkout -b feature/your-change
git add .
git commit -m "feat: describe the change"
git push -u origin feature/your-change
gh pr create --base develop --fill
```

Integrate features into `develop`, validate, then review/release to `main`. Configure branch protections in GitHub as appropriate. CI provisions pgvector, installs locked dependencies, runs Ruff/tests, and invokes no-key MCP/evaluation checks. It includes no fake AWS job.

The release tag is `v1.0.0-portfolio`; Python package metadata uses PEP 440 form `1.0.0+portfolio`.

## Roadmap / future upgrades

Run and debug locally, evaluate real models, review labels, compare one agent with the verifier workflow, and then consider improved retrieval, real adapters, durable recovery, authenticated deployment, and optional Python UI.

Cloud direction remains ECR/ECS/Fargate, managed PostgreSQL, secret storage, and CloudWatch. **No Terraform or unverified cloud scaffolding is included.** Container packaging, explicit configuration, migrations, and health endpoints are the current cloud preparation. Nothing was provisioned.

## License

Original code and synthetic fixtures are [MIT licensed](LICENSE). Dependencies, containers, PostgreSQL, model services, and their assets retain their own licenses/terms. See [third-party notes](docs/third-party.md). No model weights or proprietary data are included.
