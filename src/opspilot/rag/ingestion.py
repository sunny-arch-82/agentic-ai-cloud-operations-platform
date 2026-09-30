import asyncio
import hashlib
import json
from datetime import datetime

from sqlalchemy import text

from opspilot.core.config import Settings
from opspilot.models.embeddings import make_embedder
from opspilot.rag.chunking import parse_document
from opspilot.storage.db import Database


async def ingest(db: Database, settings: Settings):
    embedder = make_embedder(settings)
    count = 0
    files = sorted((settings.data_dir / "knowledge").glob("*.md"))
    if not files:
        raise ValueError("No knowledge documents found")
    for path in files:
        raw = path.read_text()
        meta, chunks = parse_document(raw)
        published = datetime.fromisoformat(str(meta["published_at"]).replace("Z", "+00:00"))
        if published.tzinfo is None:
            raise ValueError("Document published_at requires a timezone")
        digest = hashlib.sha256(raw.encode()).hexdigest()
        existing = await asyncio.to_thread(
            db.read,
            "SELECT content_hash FROM documents WHERE document_id=:id AND version=:version",
            {"id": meta["document_id"], "version": str(meta["version"])},
        )
        if existing and existing[0]["content_hash"] != digest:
            raise ValueError(
                f"Immutable document version changed: {meta['document_id']}; bump version"
            )
        if existing:
            indexed = await asyncio.to_thread(
                db.read,
                "SELECT chunk_id FROM chunks WHERE document_id=:id AND version=:version AND embedding_key=:key",
                {
                    "id": meta["document_id"],
                    "version": str(meta["version"]),
                    "key": settings.embedding_key,
                },
            )
            if {r["chunk_id"] for r in indexed} == {c.chunk_id for c in chunks}:
                count += len(chunks)
                continue
        vectors = await embedder.embed([f"{c.heading}\n{c.content}" for c in chunks])

        def write(meta, chunks, vectors, published, digest, raw):
            with db.engine.begin() as conn:
                conn.execute(
                    text("""INSERT INTO documents
                    (document_id,version,title,service,kind,published_at,content_hash,content)
                    VALUES (:id,:version,:title,:service,:kind,:published,:hash,:content)
                    ON CONFLICT(document_id,version) DO NOTHING"""),
                    {
                        "id": meta["document_id"],
                        "version": str(meta["version"]),
                        "title": meta["title"],
                        "service": meta["service"],
                        "kind": meta["kind"],
                        "published": published,
                        "hash": digest,
                        "content": raw,
                    },
                )
                for chunk, vector in zip(chunks, vectors, strict=True):
                    conn.execute(
                        text("""INSERT INTO chunks
                        (chunk_id,embedding_key,document_id,version,section_id,heading,content,
                         start_line,end_line,embedding)
                        VALUES (:cid,:key,:did,:version,:sid,:heading,:content,:start,:end,CAST(:vector AS vector))
                        ON CONFLICT(chunk_id,embedding_key) DO NOTHING"""),
                        {
                            "cid": chunk.chunk_id,
                            "key": settings.embedding_key,
                            "did": meta["document_id"],
                            "version": str(meta["version"]),
                            "sid": chunk.section_id,
                            "heading": chunk.heading,
                            "content": chunk.content,
                            "start": chunk.start_line,
                            "end": chunk.end_line,
                            "vector": json.dumps(vector),
                        },
                    )

        await asyncio.to_thread(write, meta, chunks, vectors, published, digest, raw)
        count += len(chunks)
    return {
        "documents": len(files),
        "chunks_processed": count,
        "embedding_key": settings.embedding_key,
    }
