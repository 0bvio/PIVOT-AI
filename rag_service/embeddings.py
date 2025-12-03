from __future__ import annotations

import threading
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from . import config


_emb_lock = threading.Lock()
_emb_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _emb_model
    if _emb_model is None:
        with _emb_lock:
            if _emb_model is None:
                _emb_model = SentenceTransformer(config.EMBEDDING_MODEL, device=None)
    return _emb_model


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    out = vectors / norms
    return out.astype(np.float32, copy=False)


def embed_texts(texts: List[str], normalize: bool = True, batch_size: int = 32) -> np.ndarray:
    if not texts:
        return np.zeros((0, 1024), dtype=np.float32)
    model = get_embedding_model()
    embs = model.encode(texts, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=False)
    embs = np.asarray(embs, dtype=np.float32)
    if normalize:
        embs = l2_normalize(embs)
    return embs
