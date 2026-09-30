import asyncio
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from opspilot import __version__
from opspilot.core.config import Settings
from opspilot.core.logging import configure, event
from opspilot.schemas.contracts import (
    Answer,
    InvestigationReport,
    InvestigationRequest,
    QueryRequest,
)
from opspilot.services.investigations import get_investigation, investigate
from opspilot.services.query import answer_query
from opspilot.storage.db import Database


def create_app(settings=None, database=None):
    settings = settings or Settings()
    db = database or Database(settings)

    @asynccontextmanager
    async def lifespan(app):
        configure(settings.log_level)
        yield
        if database is None:
            db.close()

    app = FastAPI(
        title="OpsPilot",
        version=__version__,
        lifespan=lifespan,
        description="Read-only evidence-backed investigations. Requests execute synchronously; no durable background jobs.",
    )
    app.state.settings, app.state.db = settings, db

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id, started = str(uuid.uuid4()), time.monotonic()
        try:
            response = await call_next(request)
        except Exception as exc:
            event("request_error", request_id=request_id, error_type=type(exc).__name__)
            response = JSONResponse(
                status_code=503,
                content={
                    "detail": "Dependency unavailable or invalid provider response",
                    "request_id": request_id,
                },
            )
        response.headers["X-Request-ID"] = request_id
        event(
            "http_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.monotonic() - started) * 1000, 2),
        )
        return response

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": __version__, "mode": settings.mode}

    @app.get("/ready")
    async def ready():
        try:
            rows = await asyncio.to_thread(
                db.read,
                "SELECT count(*) AS n FROM chunks WHERE embedding_key=:key",
                {"key": settings.embedding_key},
            )
            await asyncio.to_thread(db.read, "SELECT version_num FROM alembic_version")
            if rows[0]["n"] == 0:
                raise ValueError("No indexed documents")
        except Exception:
            raise HTTPException(
                503, "Database, migrations, or matching embedding index unavailable; run bootstrap"
            ) from None
        return {
            "status": "ready",
            "embedding_key": settings.embedding_key,
            "chunks": rows[0]["n"],
            "provider_access": "not probed; validated only on model calls",
        }

    @app.post("/query", response_model=Answer)
    async def query(request: QueryRequest):
        return await answer_query(db, settings, request)

    @app.post("/investigations", response_model=InvestigationReport, status_code=201)
    async def investigations(request: InvestigationRequest):
        return await investigate(db, settings, request)

    @app.get("/investigations/{investigation_id}")
    async def get_report(investigation_id: uuid.UUID):
        report = await asyncio.to_thread(get_investigation, db, str(investigation_id))
        if report is None:
            raise HTTPException(404, "Investigation not found")
        return report

    return app
