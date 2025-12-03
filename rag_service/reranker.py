from __future__ import annotations

import threading
from typing import List, Tuple

from sentence_transformers import CrossEncoder

from . import config


_rr_lock = threading.Lock()
_rr_model: CrossEncoder | None = None


def get_reranker() -> CrossEncoder:
    global _rr_model
    if _rr_model is None:
        with _rr_lock:
            if _rr_model is None:
                _rr_model = CrossEncoder(config.RERANKER_MODEL, device=None)
    return _rr_model


def rerank(query: str, docs: List[str]) -> List[Tuple[int, float]]:
    """
    Returns list of (index, score) sorted by score desc.
    """
    if not docs:
        return []
    model = get_reranker()
    pairs = [(query, d) for d in docs]
    scores = model.predict(pairs, show_progress_bar=False)
    indexed = list(enumerate([float(s) for s in scores]))
    indexed.sort(key=lambda x: x[1], reverse=True)
    return indexed
