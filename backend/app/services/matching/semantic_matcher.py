"""
Semantic matching using SentenceTransformers + cosine similarity.
Uses BAAI/bge-small-en-v1.5 (fast, high quality for asymmetric retrieval).
Model is downloaded once and cached in memory.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Tuple

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@lru_cache(maxsize=1)
def _load_model():
    """Load embedding model once and cache it in memory."""
    from sentence_transformers import SentenceTransformer
    model_name = settings.EMBEDDING_MODEL
    logger.info(f"Loading embedding model: {model_name}")
    model = SentenceTransformer(model_name)
    logger.info("Embedding model loaded.")
    return model


def embed(texts: List[str]) -> np.ndarray:
    """Return normalized embeddings for a list of texts."""
    model = _load_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors (already normalized → dot product)."""
    return float(np.dot(a, b))


def find_best_evidence(
    query: str,
    passages: List[str],
    top_k: int = 3,
    min_score: float = 0.35,
) -> List[Tuple[str, float]]:
    """
    Find the most semantically relevant passages for a query.
    Returns [(passage, score)] sorted by descending score.
    Only returns passages above min_score threshold.

    IMPORTANT: High similarity is NOT proof of competence.
    It means the passage is topically related.
    """
    if not passages:
        return []

    query_emb = embed([query])[0]
    passage_embs = embed(passages)

    scored = []
    for passage, emb in zip(passages, passage_embs):
        score = cosine_similarity(query_emb, emb)
        if score >= min_score:
            scored.append((passage, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def semantic_skill_score(
    jd_requirement: str,
    resume_sections: dict,
    top_k: int = 3,
) -> Tuple[float, List[str]]:
    """
    Compute semantic relevance score for a JD requirement against resume sections.
    Returns (score, [best_evidence_passages]).
    Score = average of top-k cosine similarities, capped at 0-1.
    """
    # Collect all non-empty resume passages
    passages: List[str] = []
    for section_text in resume_sections.values():
        if section_text and len(section_text.strip()) > 20:
            # Split into chunks for better granularity
            chunks = [s.strip() for s in section_text.split("\n") if len(s.strip()) > 20]
            passages.extend(chunks[:30])  # cap per section

    if not passages:
        return 0.0, []

    best = find_best_evidence(jd_requirement, passages, top_k=top_k)
    if not best:
        return 0.0, []

    avg_score = sum(score for _, score in best) / len(best)
    evidence_texts = [p for p, _ in best]

    return min(avg_score, 1.0), evidence_texts
