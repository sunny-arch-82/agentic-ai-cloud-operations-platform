# Development and upgrades

Run commands from the repository root. Use `uv sync --frozen` and `.venv/bin/python`; do not install project packages into system Python.

```bash
docker compose up -d db
uv run opspilot bootstrap
uv run uvicorn opspilot.api.app:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

Alembic revisions are explicit Python migration files. The initial downgrade drops application tables and data: do not use it on data you intend to keep. Follow the existing revision format when adding a migration; no autogeneration template/model registry is supplied. An image rollback does not undo database changes.

Keep `(document_id, version)` immutable. New content needs a new version and later publication time; avoid ties between version publication timestamps. Embedding/chunking changes need explicit re-indexing/version consideration. Fixture loading uses `ON CONFLICT DO NOTHING`; changed fixture records require a fresh development database or data migration.

If `/ready` returns 503, check the database, migration, and matching indexed profile. Real provider failures never silently fall back to fake success. Inspect report/tool activity for failed steps. Generic CLI/API errors intentionally omit credentials and stack traces; debug with isolated tests and source-level inspection.

Keep `.env`, `.venv`, caches, database volumes, and local evaluation outputs out of Git. Commit source, `.env.example`, `uv.lock`, fixtures, tests, and documentation. Upgrade via `feature/*` into `develop`, then reviewed releases to `main`.

This ZIP was finalized after the owner stopped execution. Previous tests do not certify every final source/documentation edit. Run the provided commands in your own validation session before publishing quality claims.
