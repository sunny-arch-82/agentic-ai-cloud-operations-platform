"""Exact pgvector and PostgreSQL FTS, joined by reciprocal rank fusion."""

import asyncio
import json
from datetime import UTC, datetime

from opspilot.core.config import Settings
from opspilot.models.embeddings import make_embedder
from opspilot.schemas.contracts import Evidence
from opspilot.storage.db import Database

DEPENDENCIES = {
    "checkout": ["checkout", "payments", "inventory", "postgres", "global"],
    "payments": ["payments", "postgres", "global"],
    "inventory": ["inventory", "postgres", "global"],
    "postgres": ["postgres", "global"],
}


def rrf(rankings: list[list[dict]], k: int = 60):
    scores, rows = {}, {}
    for ranking in rankings:
        for position, row in enumerate(ranking, 1):
            cid = row["chunk_id"]
            scores[cid] = scores.get(cid, 0) + 1 / (k + position)
            rows[cid] = row
    return [
        dict(rows[cid], rank_score=scores[cid])
        for cid in sorted(scores, key=lambda x: (-scores[x], x))
    ]


class Retriever:
    def __init__(self, db: Database, settings: Settings):
        self.db, self.settings = db, settings
        self.embedder = make_embedder(settings)

    async def search(
        self,
        query: str,
        service: str,
        as_of: datetime,
        mode: str | None = None,
        limit: int | None = None,
        kind: str | None = None,
    ):
        mode = mode or self.settings.retrieval_mode
        if mode not in {"semantic", "lexical", "hybrid"}:
            raise ValueError("Invalid retrieval mode")
        if service not in DEPENDENCIES or not 1 <= len(query) <= 2000:
            raise ValueError("Invalid retrieval scope or query")
        limit = min(limit or self.settings.top_k, 10)
        params = {
            "services": DEPENDENCIES[service],
            "as_of": as_of,
            "key": self.settings.embedding_key,
            "query": query,
            "kind": kind,
            "limit": max(limit * 4, 20),
        }
        # MATERIALIZED avoids comparing vectors from different embedding profiles/dimensions.
        base = """WITH selected AS MATERIALIZED (
            SELECT c.*, d.title,d.service,d.kind,d.published_at
            FROM chunks c JOIN documents d USING(document_id,version)
            WHERE c.embedding_key=:key AND d.service=ANY(:services)
              AND d.published_at<=:as_of AND (CAST(:kind AS text) IS NULL OR d.kind=:kind)
              AND NOT EXISTS (SELECT 1 FROM documents newer
                WHERE newer.document_id=d.document_id AND newer.published_at>d.published_at
                  AND newer.published_at<=:as_of)) """
        rankings = []
        if mode in {"semantic", "hybrid"}:
            vector = (await self.embedder.embed([query]))[0]
            params["vector"] = json.dumps(vector)
            rankings.append(
                await asyncio.to_thread(
                    self.db.read,
                    base
                    + """
                SELECT *, 1-(embedding <=> CAST(:vector AS vector)) AS rank_score FROM selected
                ORDER BY embedding <=> CAST(:vector AS vector),chunk_id LIMIT :limit""",
                    params,
                )
            )
        if mode in {"lexical", "hybrid"}:
            rankings.append(
                await asyncio.to_thread(
                    self.db.read,
                    base
                    + """
                SELECT *, ts_rank_cd(search_vector,websearch_to_tsquery('english',:query)) AS rank_score
                FROM selected WHERE search_vector @@ websearch_to_tsquery('english',:query)
                ORDER BY rank_score DESC,chunk_id LIMIT :limit""",
                    params,
                )
            )
        ranked = rrf(rankings) if mode == "hybrid" else rankings[0]
        return ranked[:limit]

    @staticmethod
    def evidence(rows, max_chars=24000):
        results, remaining = [], max_chars
        for row in rows:
            content = row["content"]
            if len(content) > remaining:
                continue  # Never silently truncate a cited passage.
            remaining -= len(content)
            results.append(
                Evidence(
                    evidence_id=f"doc-{row['chunk_id']}",
                    kind="document",
                    source=f"{row['document_id']}@{row['version']}:{row['start_line']}-{row['end_line']}",
                    service=row["service"],
                    observed_at=row["published_at"],
                    captured_at=datetime.now(UTC),
                    summary=f"{row['title']} / {row['heading']}",
                    data={
                        "document_id": row["document_id"],
                        "version": row["version"],
                        "section_id": row["section_id"],
                        "text": content,
                        "start_line": row["start_line"],
                        "end_line": row["end_line"],
                        "rank_score": row.get("rank_score"),
                    },
                )
            )
        return results
