from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from . import config
from .embeddings import embed_texts
from .milvus_client import MilvusManager
from .reranker import rerank
from .ingestion import ingest_directory


app = FastAPI(title="Pivot RAG Service", version="1.0.0")


class SearchRequest(BaseModel):
    query: str = Field(..., description="User query")
    top_k: int = Field(25, ge=1, le=100, description="Vector top-K before reranking")
    logical_collection: Optional[str] = Field(None, description="Logical collection filter")
    expr: Optional[str] = Field(None, description="Additional Milvus boolean expression filter")


@app.get("/v1/retrieval/health")
def health() -> Dict[str, Any]:
    # simple Milvus connection check by ensuring collection
    try:
        MilvusManager()
        milvus_ok = True
    except Exception as e:
        milvus_ok = False
    return {
        "status": "ok" if milvus_ok else "degraded",
        "milvus": milvus_ok,
        "embedding_model": config.EMBEDDING_MODEL,
        "reranker_model": config.RERANKER_MODEL,
        "collection": config.MILVUS_COLLECTION,
    }


@app.post("/v1/retrieval/search")
def search(req: SearchRequest) -> Dict[str, Any]:
    query = req.query.strip()
    if not query:
        return {"results": []}

    manager = MilvusManager()
    qvec = embed_texts([query])[0].tolist()
    hits = manager.search(qvec, top_k=req.top_k or 25, logical_collection=req.logical_collection, expr=req.expr)

    # Prepare reranking inputs
    docs = [h.entity.get("text", "") for h in hits]
    rr = rerank(query, docs)

    results: List[Dict[str, Any]] = []
    for idx, score in rr:
        h = hits[idx]
        ent = h.entity
        results.append({
            "text": ent.get("text", ""),
            "rerank_score": score,
            "similarity": float(h.distance),
            "metadata": {
                "source_id": ent.get("source_id"),
                "source_path": ent.get("source_path"),
                "doc_title": ent.get("doc_title"),
                "mime_type": ent.get("mime_type"),
                "chunk_index": ent.get("chunk_index"),
                "created_at": ent.get("created_at"),
                "hash": ent.get("hash"),
                "logical_collection": ent.get("logical_collection"),
            }
        })

    return {"results": results}


class IngestRequest(BaseModel):
    base_dir: str
    pattern: Optional[str] = Field("**/*")
    logical_collection: Optional[str] = None


@app.post("/v1/ingest/scan")
def ingest_scan(req: IngestRequest) -> Dict[str, Any]:
    results = ingest_directory(req.base_dir, pattern=req.pattern or "**/*", logical_collection=req.logical_collection)
    total = len(results)
    ok = sum(1 for r in results if r.get("status") == "ingested")
    skipped = sum(1 for r in results if r.get("status", "").startswith("skipped"))
    errors = [r for r in results if r.get("status") == "error"]
    return {
        "total": total,
        "ingested": ok,
        "skipped": skipped,
        "errors": errors,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("rag_service.app:app", host="0.0.0.0", port=8000, reload=False)
