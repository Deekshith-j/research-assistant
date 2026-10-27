"""Loading the company knowledge base (`data/corpus.jsonl`).

The corpus file is treated as read-only: we only parse it, never rewrite it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from assistant.config import settings


@dataclass(frozen=True)
class Chunk:
    """One record of the corpus: a passage plus the metadata needed for citations."""

    chunk_id: str
    doc_id: str
    title: str
    category: str
    owner: str
    source_url: str
    published: str  # YYYYMMDD as given in the corpus
    version: str
    text: str

    @property
    def published_iso(self) -> str:
        """Published date as YYYY-MM-DD, which is easier for the LLM to compare."""
        p = self.published
        return f"{p[:4]}-{p[4:6]}-{p[6:8]}" if len(p) == 8 else p

    def to_evidence(self, score: float = 0.0) -> dict:
        """Plain dict stored in the agent state (serialisable, readable in LangSmith)."""
        return {
            "chunk_id": self.chunk_id, "doc_id": self.doc_id, "title": self.title,
            "category": self.category, "published": self.published_iso,
            "version": self.version, "text": self.text, "score": score,
        }


@lru_cache(maxsize=1)
def load_corpus(path: Path | None = None) -> tuple[Chunk, ...]:
    """Parse every JSONL line into a Chunk (cached, the file never changes at runtime)."""
    path = path or settings.corpus_path
    chunks: list[Chunk] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                record = json.loads(line)
                chunks.append(Chunk(**{f: str(record[f]) for f in Chunk.__dataclass_fields__}))
    return tuple(chunks)


def corpus_fingerprint(path: Path | None = None) -> str:
    """SHA-256 of the corpus file; used to detect when the vector index must be rebuilt."""
    return hashlib.sha256(Path(path or settings.corpus_path).read_bytes()).hexdigest()


def chunks_by_id() -> dict[str, Chunk]:
    """Lookup table chunk_id -> Chunk (used to validate citations)."""
    return {c.chunk_id: c for c in load_corpus()}
