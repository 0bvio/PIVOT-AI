"""
Open WebUI Extension: Pivot RAG Tools

Provides two tools:
 - pivot_rag_search: Fetch reranked context from the external Pivot RAG service
 - pivot_rag_ingest_scan: Trigger a directory scan/ingestion on the Pivot RAG service

This integrates the external ingestion/retrieval pipeline with Open WebUI without
using Open WebUI's internal ingestion.

The extension is discovered by Open WebUI via manifest.json.

Notes:
 - The Open WebUI container can reach the rag-service by docker service name: http://rag-service:8000
 - Default logical collection is configurable via env var PIVOT_RAG_LOGICAL_COLLECTION.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, Optional


RAG_BASE_URL = os.environ.get("PIVOT_RAG_BASE_URL", "http://rag-service:8000")
DEFAULT_LOGICAL_COLLECTION = os.environ.get("PIVOT_RAG_LOGICAL_COLLECTION", "My_Project_History")
PIVOT_RAG_TIMEOUT = int(os.environ.get("PIVOT_RAG_TIMEOUT", "60"))


def _http_post_json(url: str, payload: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        if not body:
            return {}
        return json.loads(body)


def pivot_rag_search(query: str, top_k: int = 25, logical_collection: Optional[str] = None) -> str:
    """
    Calls the Pivot RAG retrieval API and returns a formatted context string.
    """
    if not query or not query.strip():
        return ""
    url = f"{RAG_BASE_URL}/v1/retrieval/search"
    payload = {
        "query": query.strip(),
        "top_k": int(top_k) if top_k else 25,
        "logical_collection": logical_collection or DEFAULT_LOGICAL_COLLECTION,
    }
    try:
        # use configured timeout from env
        res = _http_post_json(url, payload, timeout=PIVOT_RAG_TIMEOUT)
    except Exception as e:
        return f"[pivot_rag_search error] {e}"

    results = res.get("results", [])
    if not results:
        return "[pivot_rag] No context found."

    # Build a compact context string suitable for prompt injection
    lines = ["[pivot_rag context]"]
    for i, r in enumerate(results, start=1):
        meta = r.get("metadata", {})
        source = meta.get("source_path", meta.get("source_id", ""))
        score = r.get("rerank_score")
        try:
            score_str = f"{score:.3f}"
        except Exception:
            score_str = str(score)
        lines.append(f"[{i}] {source} (score={score_str})\n{r.get('text','').strip()}\n")

    return "\n".join(lines)


def pivot_rag_ingest_scan(base_dir: Optional[str] = None, pattern: str = "**/*", logical_collection: Optional[str] = None) -> str:
    """
    Triggers a scan/ingest on the RAG service. Defaults to base_dir=/data/raw inside the rag-service.
    """
    url = f"{RAG_BASE_URL}/v1/ingest/scan"
    payload = {
        "base_dir": base_dir or "/data/raw",
        "pattern": pattern or "**/*",
        "logical_collection": logical_collection or DEFAULT_LOGICAL_COLLECTION,
    }
    try:
        res = _http_post_json(url, payload, timeout=3600)
    except Exception as e:
        return f"[pivot_rag_ingest_scan error] {e}"

    total = res.get("total", 0)
    ing = res.get("ingested", 0)
    skipped = res.get("skipped", 0)
    err = res.get("errors", [])
    msg = f"[pivot_rag] Ingest scan complete: total={total}, ingested={ing}, skipped={skipped}, errors={len(err)}"
    if err:
        # include up to 3 error filenames for quick feedback
        names = [os.path.basename(e.get("file", "")) for e in err[:3]]
        msg += f". Example errors: {', '.join(names)}"
    return msg


# Extension entrypoint API for Open WebUI
class Extension:
    """
    Open WebUI will instantiate Extension(ctx) if available.
    We use ctx.register_tool to expose tools.
    """

    def __init__(self, ctx):  # ctx is provided by Open WebUI
        # Simple startup log to help diagnose loading in container logs
        try:
            print("[pivot_rag] Extension initializing")
        except Exception:
            pass

        # Register search tool
        try:
            ctx.register_tool(
                tool_id="pivot_rag_search",
                name="Pivot RAG Search",
                description="Fetches reranked context from Milvus via Pivot RAG service.",
                desc="Fetches reranked context from Milvus via Pivot RAG service.",
                func=pivot_rag_search,
                parameters=
                {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "User query to search."},
                        "top_k": {"type": "integer", "description": "Top-K vector results before rerank.", "default": 25},
                        "logical_collection": {"type": "string", "description": "Logical collection filter.", "default": DEFAULT_LOGICAL_COLLECTION},
                    },
                    "required": ["query"],
                },
            )
            print("[pivot_rag] Registered tool: pivot_rag_search")
        except Exception as e:
            try:
                print(f"[pivot_rag] Failed to register pivot_rag_search: {e}")
            except Exception:
                pass

        # Register ingestion tool (optional use)
        try:
            ctx.register_tool(
                tool_id="pivot_rag_ingest_scan",
                name="Pivot RAG Ingest Scan",
                description="Trigger ingestion scan on the Pivot RAG service (scans /data/raw by default).",
                desc="Trigger ingestion scan on the Pivot RAG service (scans /data/raw by default).",
                func=pivot_rag_ingest_scan,
                parameters=
                {
                    "type": "object",
                    "properties": {
                        "base_dir": {"type": "string", "description": "Base directory inside rag-service (default /data/raw)."},
                        "pattern": {"type": "string", "description": "Glob pattern to match files.", "default": "**/*"},
                        "logical_collection": {"type": "string", "description": "Logical collection name.", "default": DEFAULT_LOGICAL_COLLECTION},
                    },
                },
            )
            print("[pivot_rag] Registered tool: pivot_rag_ingest_scan")
        except Exception as e:
            try:
                print(f"[pivot_rag] Failed to register pivot_rag_ingest_scan: {e}")
            except Exception:
                pass


# JSON-serializable tool descriptors for loaders that import metadata without executing
TOOL_DESCRIPTORS = [
    {
        "id": "pivot_rag_search",
        "name": "Pivot RAG Search",
        "description": "Fetches reranked context from Milvus via Pivot RAG service.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "User query to search."},
                "top_k": {"type": "integer", "description": "Top-K vector results before rerank.", "default": 25},
                "logical_collection": {"type": "string", "description": "Logical collection filter.", "default": DEFAULT_LOGICAL_COLLECTION},
            },
            "required": ["query"],
        },
    },
    {
        "id": "pivot_rag_ingest_scan",
        "name": "Pivot RAG Ingest Scan",
        "description": "Trigger ingestion scan on the Pivot RAG service.",
        "parameters": {
            "type": "object",
            "properties": {
                "base_dir": {"type": "string", "description": "Base directory inside rag-service (default /data/raw).", "default": "/data/raw"},
                "pattern": {"type": "string", "description": "Glob pattern to match files.", "default": "**/*"},
                "logical_collection": {"type": "string", "description": "Logical collection name.", "default": DEFAULT_LOGICAL_COLLECTION},
            },
        },
    },
]


# Fallback variables for alternative loaders (if any)
TOOLS = [
    {
        "id": "pivot_rag_search",
        "name": "Pivot RAG Search",
        "description": "Fetches reranked context from Milvus via Pivot RAG service.",
        "function": pivot_rag_search,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 25},
                "logical_collection": {"type": "string", "default": DEFAULT_LOGICAL_COLLECTION},
            },
            "required": ["query"],
        },
    },
    {
        "id": "pivot_rag_ingest_scan",
        "name": "Pivot RAG Ingest Scan",
        "description": "Trigger ingestion scan on the Pivot RAG service.",
        "function": pivot_rag_ingest_scan,
        "parameters": {
            "type": "object",
            "properties": {
                "base_dir": {"type": "string", "default": "/data/raw"},
                "pattern": {"type": "string", "default": "**/*"},
                "logical_collection": {"type": "string", "default": DEFAULT_LOGICAL_COLLECTION},
            },
        },
    },
]
