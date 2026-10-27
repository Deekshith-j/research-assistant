"""Hybrid retrieval over the corpus: local embeddings + Chroma + BM25.

Why hybrid?
  * Dense vectors (bge-small via fastembed, runs locally on CPU) capture meaning:
    "how long are records kept" ~ "retains searchable run records for 21 days".
  * BM25 catches exact tokens dense models blur: "INC-2025-12", "2.3.1", "429", "SAML".
  Both ranked lists are merged with Reciprocal Rank Fusion (RRF), which needs no
  score calibration between the two systems.

Everything is local: the embedding model is downloaded once and cached, and the
vector store is a persistent Chroma database under `storage/chroma`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import chromadb
from fastembed import TextEmbedding
from langsmith import traceable
from rank_bm25 import BM25Okapi

from assistant.config import settings
from assistant.knowledge.corpus import Chunk, chunks_by_id, corpus_fingerprint, load_corpus

COLLECTION_NAME = "asterline_corpus"
RRF_K = 60  # standard RRF damping constant
# bge models expect this instruction in front of *queries* (not documents).
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

SearchMode = Literal["hybrid", "vector", "bm25"]


@dataclass
class ScoredChunk:
    """A retrieved chunk with its fused relevance score (higher = better)."""

    chunk: Chunk
    score: float


def _tokenize(text: str) -> list[str]:
    """Lower-case tokens; keeps hyphens/dots inside tokens so 'inc-2025-12' and '2.3.1' survive."""
    return re.findall(r"[a-z0-9]+(?:[.\-_][a-z0-9]+)*", text.lower())


class HybridRetriever:
    """Owns the embedding model, the Chroma collection and the BM25 index."""

    def __init__(self) -> None:
        self.chunks = load_corpus()
        self._by_id = chunks_by_id()
        self._embedder = TextEmbedding(model_name=settings.embedding_model)
        self._is_bge = "bge" in settings.embedding_model.lower()

        # --- Vector store (persistent, local) ---
        settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        self._collection = self._ensure_index(client)

        # --- Keyword index (in memory; 75 chunks build in milliseconds) ---
        self._bm25_ids = [c.chunk_id for c in self.chunks]
        self._bm25 = BM25Okapi([_tokenize(f"{c.title} {c.text}") for c in self.chunks])

    # ------------------------------------------------------------------ indexing
    def _ensure_index(self, client: chromadb.ClientAPI):
        """Build the Chroma collection on first run, or rebuild it if the corpus/model changed."""
        fingerprint = f"{corpus_fingerprint()}::{settings.embedding_model}"
        existing = {c.name for c in client.list_collections()}
        if COLLECTION_NAME in existing:
            col = client.get_collection(COLLECTION_NAME)
            if (col.metadata or {}).get("fingerprint") == fingerprint and col.count() == len(self.chunks):
                return col  # index is up to date -> reuse it (fast restart)
            client.delete_collection(COLLECTION_NAME)

        col = client.create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine", "fingerprint": fingerprint}
        )
        # Embed "title + text" so the document title also contributes to similarity.
        vectors = self.embed_passages([f"{c.title}. {c.text}" for c in self.chunks])
        col.add(
            ids=[c.chunk_id for c in self.chunks],
            embeddings=vectors,
            documents=[c.text for c in self.chunks],
            metadatas=[
                {"doc_id": c.doc_id, "title": c.title, "category": c.category,
                 "published": c.published, "version": c.version}
                for c in self.chunks
            ],
        )
        return col

    # ------------------------------------------------------------------ search
    def embed_query(self, text: str) -> list[float]:
        """Embed a search query (adds the bge query instruction when needed)."""
        q = f"{BGE_QUERY_PREFIX}{text}" if self._is_bge else text
        return next(iter(self._embedder.embed([q]))).tolist()

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """Embed short passages (also reused to rank a user's memories by relevance)."""
        return [v.tolist() for v in self._embedder.embed(texts)]

    def _vector_ranking(self, query: str, n: int) -> list[str]:
        """Chunk ids ordered by cosine similarity to the query."""
        res = self._collection.query(query_embeddings=[self.embed_query(query)], n_results=n)
        return res["ids"][0]

    def _bm25_ranking(self, query: str, n: int) -> list[str]:
        """Chunk ids ordered by BM25 keyword score (zero-score chunks dropped)."""
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self._bm25_ids, scores), key=lambda x: x[1], reverse=True)
        return [cid for cid, s in ranked[:n] if s > 0]

    def search(self, query: str, k: int | None = None, mode: SearchMode = "hybrid") -> list[ScoredChunk]:
        """Retrieve the top-k chunks for one query."""
        return self.multi_search([query], k=k, mode=mode)

    @traceable(run_type="retriever", name="hybrid_search")
    def multi_search(
        self,
        queries: list[str],
        k: int | None = None,
        mode: SearchMode = "hybrid",
        secondary_weight: float = 1.0,
    ) -> list[ScoredChunk]:
        """Search several query phrasings and fuse all ranked lists into one top-k list.

        The planner produces a few sub-queries (e.g. one per entity in a comparison);
        fusing them gives evidence for every part of the question. The first query is
        the main question; `secondary_weight` < 1 stops the extra queries from
        out-voting it (see docs/EVALUATION.md).
        """
        k = k or settings.retrieval_top_k
        pool = max(k * 3, 20)  # look deeper than k in each list before fusing
        weighted: list[tuple[list[str], float]] = []
        unique = list(dict.fromkeys(q.strip() for q in queries if q.strip()))  # dedupe, keep order
        for i, q in enumerate(unique):
            weight = 1.0 if i == 0 else secondary_weight
            if mode in ("hybrid", "vector"):
                weighted.append((self._vector_ranking(q, pool), weight))
            if mode in ("hybrid", "bm25"):
                weighted.append((self._bm25_ranking(q, pool), weight))
        return self._fuse(weighted, k)

    def expand_siblings(self, results: list[ScoredChunk], max_docs: int = 3) -> list[ScoredChunk]:
        """Add the other chunks of the best-ranked documents.

        Each document is split into 3 short chunks, and the answer often sits in a
        chunk that doesn't repeat the search terms (e.g. the *cause* of INC-2025-12 is
        in a chunk that never mentions "INC-2025-12"). Siblings get score 0 and go last.
        """
        seen = {r.chunk.chunk_id for r in results}
        top_docs = list(dict.fromkeys(r.chunk.doc_id for r in results))[:max_docs]
        extra = [
            ScoredChunk(c, 0.0) for c in self.chunks
            if c.doc_id in top_docs and c.chunk_id not in seen
        ]
        return results + extra

    def _fuse(self, weighted: list[tuple[list[str], float]], k: int) -> list[ScoredChunk]:
        """Weighted Reciprocal Rank Fusion: score(d) = sum over lists of weight / (RRF_K + rank)."""
        scores: dict[str, float] = {}
        for ranking, weight in weighted:
            for rank, cid in enumerate(ranking, start=1):
                scores[cid] = scores.get(cid, 0.0) + weight / (RRF_K + rank)
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
        return [ScoredChunk(self._by_id[cid], round(s, 5)) for cid, s in top]


@lru_cache(maxsize=1)
def get_retriever() -> HybridRetriever:
    """Process-wide retriever (loading the embedding model is the slow part)."""
    return HybridRetriever()
