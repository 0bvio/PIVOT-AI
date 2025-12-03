from __future__ import annotations

import glob
import os
import time
from typing import Dict, List

from . import config
from .chunker import chunk_text
from .embeddings import embed_texts
from .extractors import extract_text_by_path
from .milvus_client import MilvusManager
from .utils import (
    build_title_line,
    filter_duplicate_headers,
    guess_mime_type,
    source_id_for_path,
    chunk_hash,
)


def _prepare_text(base_dir: str, filepath: str) -> (str, str):
    parts = extract_text_by_path(filepath)
    parts = filter_duplicate_headers(parts)
    if not parts:
        return "", ""
    source_id = source_id_for_path(base_dir, filepath)
    title = build_title_line(source_id, base_dir, filepath)
    text = title + "\n".join(parts)
    return source_id, text


def ingest_file(base_dir: str, filepath: str, logical_collection: str | None = None, milvus: MilvusManager | None = None):
    lc = logical_collection or config.DEFAULT_LOGICAL_COLLECTION
    manager = milvus or MilvusManager()
    source_id, text = _prepare_text(base_dir, filepath)
    if not text:
        return {"file": filepath, "status": "skipped-empty"}

    # Chunk
    chunks = chunk_text(text, config.CHUNK_SIZE, config.CHUNK_OVERLAP, source_id)
    if not chunks:
        return {"file": filepath, "status": "skipped-nochunks"}

    mime = guess_mime_type(filepath)
    created = int(time.time())

    # Embed
    vectors = embed_texts([c["text"] for c in chunks])

    # Prepare rows
    items: List[Dict] = []
    for i, c in enumerate(chunks):
        txt = c["text"]
        if len(txt) > config.TEXT_MAX_LEN:
            txt = txt[: config.TEXT_MAX_LEN]
        items.append({
            "vector": vectors[i].tolist(),
            "source_id": source_id,
            "source_path": os.path.relpath(filepath, base_dir),
            "doc_title": "",
            "mime_type": mime,
            "chunk_index": c["metadata"].get("chunk_index", i),
            "created_at": created,
            "hash": chunk_hash(txt),
            "logical_collection": lc,
            "text": txt,
        })

    # Replace existing
    manager.delete_by_source_id(source_id, lc)
    manager.upsert_chunks(items)
    return {"file": filepath, "status": "ingested", "chunks": len(items)}


def ingest_directory(base_dir: str, pattern: str = "**/*", logical_collection: str | None = None) -> List[Dict]:
    files = [f for f in glob.glob(os.path.join(base_dir, pattern), recursive=True) if os.path.isfile(f)]
    out: List[Dict] = []
    manager = MilvusManager()
    for f in files:
        try:
            res = ingest_file(base_dir, f, logical_collection=logical_collection, milvus=manager)
            out.append(res)
        except Exception as e:
            out.append({"file": f, "status": "error", "error": str(e)})
    return out
