"""
Semantic Cache — Phase 3.

Uses ChromaDB PersistentClient (local folder, no Docker required).

Embeddings are computed externally and passed as raw vectors to ChromaDB
(embedding_function=None on the collection). This avoids ALL embedding-
function registration conflicts between runs — ChromaDB never stores or
checks an embedding function name.

Work-laptop embedding: pure-Python character 3-gram hash (no onnxruntime
needed). Identical prompts produce identical vectors → cache hits work.
Semantically similar but differently worded prompts won't hit — that's fine
for dev. On personal laptop, swap _embed() for a real sentence-transformer.

MIGRATION NOTE (see MIGRATION_GUIDE.md):
  Switch chromadb.PersistentClient → chromadb.HttpClient(host, port=8001)
  and replace _embed() with SentenceTransformerEmbeddingFunction.
"""
import asyncio
import hashlib
import logging
import math
import time
from typing import Optional

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_DISTANCE_THRESHOLD = 1.0 - settings.cache_similarity_threshold
_DIM = 384


def _embed(texts: list[str]) -> list[list[float]]:
    """
    Pure-Python character 3-gram hash embedding — no external deps.
    Produces a 384-dim L2-normalised float vector per text.

    MIGRATION: replace this function body with:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        _ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        return _ef(texts)
    """
    results = []
    for text in texts:
        vec = [0.0] * _DIM
        t = text.lower()
        for i in range(max(1, len(t) - 2)):
            vec[hash(t[i: i + 3]) % _DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        results.append([x / norm for x in vec])
    return results


class SemanticCache:
    """
    Semantic cache backed by ChromaDB PersistentClient.

    Public interface:
      await cache.lookup(prompt)          -> Optional[str]
      await cache.store(prompt, response) -> None
    """

    def __init__(self) -> None:
        self._client = None
        self._collection = None
        self._ready: bool = False

    def _ensure_ready(self) -> bool:
        if not settings.enable_semantic_cache:
            return False
        if self._ready:
            return True
        try:
            import chromadb

            self._client = chromadb.PersistentClient(path="./chromadb_data")
            # embedding_function=None — we embed manually and pass raw vectors.
            # This means ChromaDB never stores an embedding function name,
            # so there is never a conflict between runs.
            self._collection = self._client.get_or_create_collection(
                name=settings.chroma_collection,
                embedding_function=None,
                metadata={"hnsw:space": "cosine"},
            )
            self._ready = True
            logger.info("[CACHE] ChromaDB ready (pure-Python embeddings) — collection '%s'", settings.chroma_collection)
            return True
        except Exception as exc:
            logger.warning("[CACHE WARN] ChromaDB init failed: %s", exc)
            return False

    @staticmethod
    def _make_id(prompt: str) -> str:
        return hashlib.sha256(prompt.strip().lower().encode()).hexdigest()[:32]

    def _sync_lookup(self, prompt: str) -> Optional[str]:
        if not self._ensure_ready():
            return None

        embedding = _embed([prompt])[0]
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=1,
            include=["distances", "metadatas"],
        )

        ids       = results.get("ids",       [[]])
        distances = results.get("distances", [[]])
        metadatas = results.get("metadatas", [[]])

        if not ids[0]:
            return None

        if distances[0][0] >= _DISTANCE_THRESHOLD:
            return None

        meta = metadatas[0][0]
        age_seconds = time.time() - meta.get("created_at", 0.0)
        if age_seconds > settings.cache_ttl_hours * 3600:
            try:
                self._collection.delete(ids=[ids[0][0]])
            except Exception:
                pass
            return None

        return meta.get("response")

    def _sync_store(self, prompt: str, response: str) -> None:
        if not self._ensure_ready():
            return

        doc_id = self._make_id(prompt)
        embedding = _embed([prompt])[0]

        try:
            self._collection.delete(ids=[doc_id])
        except Exception:
            pass

        self._collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[prompt],
            metadatas=[{"response": response, "created_at": time.time()}],
        )

    async def lookup(self, prompt: str) -> Optional[str]:
        try:
            return await asyncio.to_thread(self._sync_lookup, prompt)
        except Exception as exc:
            logger.warning("[CACHE WARN] lookup error: %s", exc)
            return None

    async def store(self, prompt: str, response: str) -> None:
        try:
            await asyncio.to_thread(self._sync_store, prompt, response)
        except Exception as exc:
            logger.warning("[CACHE WARN] store error: %s", exc)


semantic_cache = SemanticCache()
