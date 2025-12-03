import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import importlib
import pytest


m = importlib.import_module("openwebui.extensions.pivot_rag.main")


def test_tool_descriptors_present():
    assert hasattr(m, "TOOL_DESCRIPTORS")
    assert isinstance(m.TOOL_DESCRIPTORS, list)


def test_pivot_rag_search_empty_query():
    assert m.pivot_rag_search("") == ""
    assert m.pivot_rag_search("   ") == ""


def test_pivot_rag_search_error_handling(monkeypatch):
    def raise_exc(url, payload, timeout=60):
        raise RuntimeError("boom")

    monkeypatch.setattr(m, "_http_post_json", raise_exc)
    res = m.pivot_rag_search("hello")
    assert res.startswith("[pivot_rag_search error]")


def test_pivot_rag_search_success_format(monkeypatch):
    sample_payload = {
        "results": [
            {"text": "Alpha text", "rerank_score": 3.14159, "metadata": {"source_path": "a.txt"}},
            {"text": "Beta text", "rerank_score": 2.71828, "metadata": {"source_path": "b.txt"}},
        ]
    }

    monkeypatch.setattr(m, "_http_post_json", lambda url, payload, timeout=60: sample_payload)
    out = m.pivot_rag_search("query")
    assert "[pivot_rag context]" in out
    assert "a.txt" in out and "b.txt" in out
    assert "score=3.142" in out and "score=2.718" in out


class FakeCtx:
    def __init__(self):
        self.registered = []

    def register_tool(self, **kwargs):
        self.registered.append(kwargs)


def test_extension_registers_tools():
    ctx = FakeCtx()
    # instantiate Extension which should call register_tool
    m.Extension(ctx)
    ids = {t["tool_id"] for t in ctx.registered}
    assert "pivot_rag_search" in ids
    assert "pivot_rag_ingest_scan" in ids
