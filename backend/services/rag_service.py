"""
RAG Service — Retrieval-Augmented Generation for CivicOS AI (Telangana ePASS)
Uses sentence-transformers + FAISS to retrieve relevant ePASS knowledge chunks
for free-form Q&A. Runs 100% locally. Degrades gracefully to empty results if
the embedding deps aren't installed — the step-by-step navigator does not depend
on it.

Each knowledge entry may carry a "workflow_id":
  - non-empty → the topic maps to a guided service the navigator can run
  - empty     → purely informational (fees, documents, eligibility, …)
"""

import os
import json
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Lazy imports so startup doesn't fail if deps aren't installed yet
_sentence_transformers = None
_faiss = None
_np = None


def _try_import():
    """Lazy-import heavy deps. Raises ImportError with a clear message if missing."""
    global _sentence_transformers, _faiss, _np
    if _sentence_transformers is None:
        try:
            from sentence_transformers import SentenceTransformer
            _sentence_transformers = SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. Run: pip install sentence-transformers faiss-cpu"
            )
    if _faiss is None:
        try:
            import faiss
            _faiss = faiss
        except ImportError:
            raise ImportError(
                "faiss-cpu not installed. Run: pip install faiss-cpu"
            )
    if _np is None:
        import numpy as np
        _np = np


class RAGService:
    """
    Singleton RAG service that loads knowledge chunks, encodes them with
    all-MiniLM-L6-v2, and stores vectors in a FAISS flat index for fast
    cosine-similarity retrieval.
    """

    _instance: Optional["RAGService"] = None

    def __init__(self) -> None:
        self._model = None
        self._index = None
        self._chunks: List[str] = []
        self._topics: List[str] = []
        self._workflow_ids: List[str] = []  # per-chunk guided-service id ("" if informational)
        self._loaded = False

    @classmethod
    def get_instance(cls) -> "RAGService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self) -> None:
        """Load knowledge base and build FAISS index. Call once at startup."""
        if self._loaded:
            return

        logger.info("RAGService: loading knowledge base and building FAISS index...")

        try:
            _try_import()
        except ImportError as e:
            logger.error(f"RAGService disabled — missing dependency: {e}")
            self._loaded = True  # Mark as loaded (in degraded mode)
            return

        # 1. Load knowledge base JSON
        kb_path = os.path.join(os.path.dirname(__file__), "..", "knowledge", "epass_knowledge.json")
        kb_path = os.path.abspath(kb_path)

        if not os.path.exists(kb_path):
            logger.error(f"RAGService: knowledge base not found at {kb_path}")
            self._loaded = True
            return

        with open(kb_path, "r", encoding="utf-8") as f:
            entries = json.load(f)

        # 2. Extract text chunks and metadata
        self._chunks = [e["text"] for e in entries]
        self._topics = [e["topic"] for e in entries]
        self._workflow_ids = [e.get("workflow_id", "") for e in entries]
        logger.info(f"RAGService: loaded {len(self._chunks)} knowledge chunks")

        # 3. Load embedding model (CPU, ~80MB download on first run)
        logger.info("RAGService: loading all-MiniLM-L6-v2 embedding model...")
        self._model = _sentence_transformers("all-MiniLM-L6-v2")
        logger.info("RAGService: embedding model loaded")

        # 4. Encode all chunks into vectors
        logger.info("RAGService: encoding knowledge chunks into FAISS index...")
        embeddings = self._model.encode(self._chunks, convert_to_numpy=True, normalize_embeddings=True)

        # 5. Build FAISS inner-product index (equivalent to cosine similarity on normalized vectors)
        dim = embeddings.shape[1]
        self._index = _faiss.IndexFlatIP(dim)
        self._index.add(embeddings.astype(_np.float32))

        logger.info(f"RAGService: FAISS index built with {self._index.ntotal} vectors (dim={dim})")
        self._loaded = True
        print(f"[RAGService] Ready — {len(self._chunks)} chunks indexed (dim={dim})", flush=True)

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """
        Retrieve the top-k most relevant knowledge chunks for the given query.
        Returns a list of text strings (backward compatible).
        """
        results = self.retrieve_with_meta(query, top_k)
        return [r["text"] for r in results]

    def retrieve_with_meta(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve top-k knowledge chunks WITH metadata: text, topic, actionable, action_target, score.
        Returns empty list if service is in degraded mode.
        """
        if not self._loaded:
            self.load()

        if self._index is None or self._model is None:
            logger.warning("RAGService: returning empty results (degraded mode)")
            return []

        try:
            query_vec = self._model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
            query_vec = query_vec.astype(_np.float32)

            actual_k = min(top_k, len(self._chunks))
            scores, indices = self._index.search(query_vec, actual_k)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and score > 0.1:
                    results.append({
                        "text": self._chunks[idx],
                        "topic": self._topics[idx],
                        "workflow_id": self._workflow_ids[idx],
                        "score": float(score),
                    })
                    logger.debug(f"RAG: topic='{self._topics[idx]}', workflow_id='{self._workflow_ids[idx]}', score={score:.3f}")

            logger.info(f"RAGService: retrieved {len(results)} chunks for query: '{query[:60]}'")
            return results

        except Exception as e:
            logger.error(f"RAGService: retrieval error: {e}")
            return []

    @property
    def is_available(self) -> bool:
        return self._loaded and self._index is not None
