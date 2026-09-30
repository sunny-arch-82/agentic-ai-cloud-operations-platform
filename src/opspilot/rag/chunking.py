"""Markdown section parser retaining source line ranges and stable section IDs."""

import hashlib
import re
from dataclasses import dataclass

import yaml


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    section_id: str
    heading: str
    content: str
    start_line: int
    end_line: int


def parse_document(raw: str, max_words: int = 400, overlap_lines: int = 2):
    lines = raw.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("Knowledge documents require YAML front matter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("Unterminated front matter") from exc
    meta = yaml.safe_load("\n".join(lines[1:end]))
    required = {"document_id", "version", "title", "service", "kind", "published_at"}
    if not isinstance(meta, dict) or not required <= meta.keys():
        raise ValueError(f"Required metadata: {sorted(required)}")
    if meta["service"] not in {"checkout", "payments", "inventory", "postgres", "global"}:
        raise ValueError("Unknown document service")
    if meta["kind"] not in {"runbook", "incident", "service"}:
        raise ValueError("Unknown document kind")
    chunks = []
    section_lines = []
    heading = meta["title"]
    section_index = 0
    in_fence = False

    def flush():
        nonlocal section_index
        if not any(value.strip() for _, value in section_lines):
            return
        slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
        section_id = f"{meta['document_id']}:{slug}"
        start = 0
        while start < len(section_lines):
            stop, words = start, 0
            while stop < len(section_lines) and (words < max_words or stop == start):
                words += len(section_lines[stop][1].split())
                stop += 1
            content = "\n".join(v for _, v in section_lines[start:stop]).strip()
            if content:
                cid = stable_id(
                    meta["document_id"],
                    str(meta["version"]),
                    section_id,
                    str(section_index),
                    str(start),
                    content,
                )
                chunks.append(
                    Chunk(
                        cid,
                        section_id,
                        heading,
                        content,
                        section_lines[start][0],
                        section_lines[stop - 1][0],
                    )
                )
            if stop == len(section_lines):
                break
            start = max(start + 1, stop - overlap_lines)
        section_index += 1

    for index in range(end + 1, len(lines)):
        line = lines[index]
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        match = re.match(r"^#{1,6}\s+(.+)$", line) if not in_fence else None
        if match:
            flush()
            section_lines = []
            heading = match.group(1)
        else:
            section_lines.append((index + 1, line))
    flush()
    if not chunks:
        raise ValueError("Document contains no readable sections")
    return meta, chunks
