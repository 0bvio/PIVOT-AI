Pivot RAG Open WebUI extension

This folder contains an Open WebUI extension that exposes two tools to the UI:

- pivot_rag_search: Fetches reranked context from the Pivot RAG service.
- pivot_rag_ingest_scan: Triggers ingestion scan (/data/raw by default) on the Pivot RAG service.

Files:
- main.py: Python extension code (registers tools at runtime via ctx.register_tool)
- manifest.json: Extension manifest used by Open WebUI
- tools.json: Static tool descriptors to help the Open WebUI Import UI detect tools without running Python

If the Open WebUI Import UI still doesn't detect the tools, open the container logs for `open-webui` and check the devtools console for errors when attempting to import the extension folder.
