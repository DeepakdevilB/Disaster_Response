"""Multilingual embedding service for duplicate detection and semantic search (T-037).

Uses 384-dimensional sentence embeddings (paraphrase-multilingual-MiniLM-L12-v2).
Includes in-memory LRU caching and an offline deterministic fallback for test environments.
"""

from __future__ import annotations

import functools
import hashlib
import logging
import math
import os
import re
from collections.abc import Sequence

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
MODEL_VERSION = "v1.0.0"

_st_model = None
_st_load_attempted = False


def _get_sentence_transformer():
    """Lazily load SentenceTransformer model if available."""
    global _st_model, _st_load_attempted
    if _st_load_attempted:
        return _st_model

    _st_load_attempted = True
    allow_download = os.getenv("DOWNLOAD_HF_EMBEDDINGS") == "1"
    try:
        from sentence_transformers import SentenceTransformer

        logger.info("Attempting to load sentence transformer model: %s", MODEL_NAME)
        _st_model = SentenceTransformer(MODEL_NAME, local_files_only=not allow_download)
        logger.info("Sentence transformer model loaded successfully.")
    except Exception as exc:
        logger.info(
            "SentenceTransformer not cached locally (%s). Using fast offline fallback: %s",
            MODEL_NAME,
            exc,
        )
        _st_model = None
    return _st_model


def _deterministic_offline_embedding(text: str) -> list[float]:
    """Fast deterministic 384-dimensional L2-normalized pseudo-embedding.

    Constructed from character & word n-grams hashed into 384 buckets so that
    semantically similar reports (e.g. 'flood rising' vs 'flood water rising')
    yield high cosine similarity, while unrelated texts yield low similarity.
    Zero external network download required.
    """
    clean_text = text.lower().strip()
    words = re.findall(r"\w+", clean_text)
    vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)

    # 1. Word tokens hashing (SHA-256)
    for word in words:
        h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
        idx = h % EMBEDDING_DIM
        weight = 1.0 + (len(word) / 10.0)
        vector[idx] += weight

    # 2. Bigrams hashing for phrase semantics
    for i in range(len(words) - 1):
        bigram = f"{words[i]}_{words[i+1]}"
        h = int(hashlib.sha256(bigram.encode("utf-8")).hexdigest(), 16)
        idx = h % EMBEDDING_DIM
        vector[idx] += 1.5

    # 3. Keyword semantic boost (crisis concepts cluster together)
    crisis_clusters = {
        "flood": ["flood", "water", "drown", "submerged", "paani", "boat", "dam"],
        "fire": ["fire", "flame", "smoke", "aag", "blast", "explosion", "burn"],
        "medical": ["bleed", "injured", "heart", "unconscious", "casualty", "trauma", "doctor"],
        "rescue": ["trapped", "collapse", "debris", "buried", "phanse", "chhat", "roof"],
    }
    for cluster_id, (_cluster_name, keywords) in enumerate(crisis_clusters.items()):
        offset = (cluster_id * 64) % EMBEDDING_DIM
        for kw in keywords:
            if kw in clean_text:
                for shift in range(12):
                    vector[(offset + shift) % EMBEDDING_DIM] += 2.0

    # L2 normalize
    norm = np.linalg.norm(vector)
    if norm > 1e-9:
        vector = vector / norm
    else:
        # Fallback uniform unit vector
        vector[0] = 1.0

    return vector.tolist()


@functools.lru_cache(maxsize=2048)
def generate_embedding(text: str) -> list[float]:
    """Generate a 384-dimensional unit-normalized embedding for a report text.

    Results are cached in memory for high-frequency dedup queries.
    """
    if not text or not text.strip():
        # Zero/unit fallback
        vec = [0.0] * EMBEDDING_DIM
        vec[0] = 1.0
        return vec

    model = _get_sentence_transformer()
    if model is not None:
        try:
            emb = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
            return emb.tolist()
        except Exception as exc:
            logger.warning("Error encoding text with SentenceTransformer: %s", exc)

    return _deterministic_offline_embedding(text)


def cosine_similarity(vec1: Sequence[float], vec2: Sequence[float]) -> float:
    """Compute cosine similarity between two 384-dimensional vectors.

    Values range from -1.0 to 1.0. For normalized vectors, this equals the dot product.
    """
    if len(vec1) != len(vec2) or len(vec1) == 0:
        return 0.0

    dot = sum(a * b for a, b in zip(vec1, vec2, strict=False))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 <= 1e-9 or norm2 <= 1e-9:
        return 0.0

    sim = dot / (norm1 * norm2)
    return max(-1.0, min(1.0, float(sim)))
