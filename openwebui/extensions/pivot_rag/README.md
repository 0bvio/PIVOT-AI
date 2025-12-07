Pivot RAG Open WebUI Extension

This folder contains an Open WebUI extension that exposes two tools to the UI:

- pivot_rag_search — Fetches reranked context from the Pivot RAG service.
- pivot_rag_ingest_scan — Triggers ingestion scan (/data/raw by default) on the Pivot RAG service.

Files
- main.py — Python extension code (registers tools at runtime via ctx.register_tool)
- manifest.json / extension.json — Extension manifest used by Open WebUI
- tool_descriptors.json — Static tool descriptors used by the import UI
- tools.json — Convenience file for manual import of both tools at once

Auto-load checklist (no terminal required)
1) Ensure extensions are enabled for Open WebUI (via your compose override or app settings):
   - ENABLE_EXTENSIONS=true
   - EXTENSIONS_DIR (or EXTENSIONS_PATH) points to the mounted extensions folder
2) Ensure this directory exists on the host: openwebui/extensions/pivot_rag
3) Ensure the folder contains:
   - main.py
   - manifest.json (or extension.json)
   - tool_descriptors.json
4) Restart Open WebUI from your container manager or UI so it rescans extensions.

Notes about the manifest
- The manifest’s tools field must be an array of descriptor files:
  "tools": ["tool_descriptors.json"]
- The files field should include any non-Python assets that the loader may read:
  "files": ["main.py", "tool_descriptors.json"]

If tools still don’t appear, try manual import in the UI
Option A — Import from file
1) In Open WebUI, go to Settings → Tools.
2) Choose Import (or Import JSON) and select openwebui/extensions/pivot_rag/tools.json from this repo.
3) Two tools will be created: pivot_rag_search and pivot_rag_ingest_scan.
4) In a chat, enable Tools and invoke Pivot RAG Search to verify.

Option B — Create tools manually
Create a tool with the following details:
- Tool ID: pivot_rag_search
- Name: Pivot RAG Search
- Description: Fetches reranked context from Milvus via Pivot RAG service.
- Parameters (JSON Schema):
  {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "User query to search."},
      "top_k": {"type": "integer", "default": 25},
      "logical_collection": {"type": "string", "default": "My_Project_History"}
    },
    "required": ["query"]
  }

Repeat for a second tool:
- Tool ID: pivot_rag_ingest_scan
- Name: Pivot RAG Ingest Scan
- Description: Trigger ingestion scan on the Pivot RAG service.
- Parameters (JSON Schema):
  {
    "type": "object",
    "properties": {
      "base_dir": {"type": "string", "default": "/data/raw"},
      "pattern": {"type": "string", "default": "**/*"},
      "logical_collection": {"type": "string", "default": "My_Project_History"}
    }
  }

Troubleshooting
- No tools appear after restart: verify ENABLE_EXTENSIONS is true and that EXTENSIONS_DIR points to the mounted folder.
- Tools still hidden: confirm the manifest has "tools": ["tool_descriptors.json"].
- RAG calls fail: ensure the service is reachable at the URL configured via PIVOT_RAG_BASE_URL (defaults to http://rag-service:8000 inside Docker).
