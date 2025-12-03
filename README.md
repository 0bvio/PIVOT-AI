# PIVOT - External RAG Stack (Milvus + Ollama + Open WebUI + Pivot RAG Service)

PIVOT is a self-hosted Retrieval-Augmented Generation (RAG) project that keeps your chat UI responsive by moving heavy document ingestion and retrieval into a separate service.

It uses:
- Milvus (with etcd + MinIO) for vector storage
- Ollama for LLM inference
- Open WebUI for the chat interface
- Pivot RAG Service (FastAPI) for: extraction -> chunking -> embeddings -> Milvus writes; and retrieval + reranking

Why this design? Open WebUI's built-in ingestion can hang the UI under load because it runs inside the UI container. PIVOT bypasses that completely.

## Key features
- External ingestion (no Open WebUI file processing)
- File types: .txt, .md, .pdf, .docx, .csv, .json (extensible)
- Chunking: size 2048, overlap 200
- Embeddings: BAAI/bge-large-en (1024-dim, L2-normalized; Milvus metric IP)
- Reranking: BAAI/bge-reranker-v2-m3 (after Top-K vector search)
- Milvus: HNSW index (IP), search ef=128, Top-K=25
- Open WebUI extension: "Pivot RAG Context Tool" for one-click ingest + context fetch

## Repository layout
- docker-compose.yml - Base stack (Ollama, Milvus, Open WebUI)
- docker-compose.override.yml - Adds Pivot RAG Service, enables Open WebUI extensions, disables UI ingestion
- rag_service/ - External ingestion + retrieval service
  - app.py - FastAPI app (health, search, ingest scan)
  - ingestion.py - Directory/file ingestion pipeline
  - extractors/ - PDF, DOCX, MD, TXT, CSV, JSON extractors
  - chunker.py - 2048/200 chunking
  - embeddings.py - bge-large-en embeddings (L2 normalized)
  - reranker.py - bge-reranker-v2-m3
  - milvus_client.py - Milvus schema/index/search/delete
  - config.py - Env-driven settings
  - requirements.txt - Python deps
  - Dockerfile - Builds the service image
- openwebui/extensions/pivot_rag/ - Open WebUI extension (tools)
  - manifest.json, main.py
- data/raw/ - Place your source documents here
- rag_ingest.py - Host-side ingestion CLI
- etl_pipeline.py - Legacy script (targets Open WebUI ingestion; deprecated here)

## Prerequisites
- Docker and Docker Compose
- Internet access on first run (models download inside the RAG service)
- Optional: Python 3.11+ to run rag_ingest.py

## Start the stack (exact commands)
Run these from the project root: /home/sly0bvio/PROJECTS/PIVOT

1) Stop any existing stack
```
sudo docker compose -f docker-compose.yml -f docker-compose.override.yml down
```

2) Build the RAG service image (no cache ensures fresh COPY)
```
sudo docker compose -f docker-compose.yml -f docker-compose.override.yml build rag-service --no-cache
```

3) Start everything with the override applied
```
sudo docker compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

4) Verify containers
```
sudo docker compose ps
```
- Expected: pivot_ai_webui, pivot_ai_rag_service, pivot_ai_milvus, pivot_ai_milvus_etcd, pivot_ai_milvus_minio, pivot_ai_ollama.

5) Check RAG service health (first run may take time)
```
curl -s http://localhost:8000/v1/retrieval/health | jq
```

## Add documents
Put files under:
```
./data/raw
```
Supported: .txt, .md, .pdf, .docx, .csv, .json.

The pipeline cleans text, chunks (2048/200), embeds (bge-large-en), and writes to Milvus with metadata.

## Ingest documents (choose one)

Option A - From Open WebUI (simple)
- Open http://localhost:3000
- Settings -> Extensions -> ensure "Pivot RAG Context Tool" is present
- In any chat, open Tools -> run "Pivot RAG Ingest Scan"
  - Defaults: base_dir /data/raw, pattern **/*, logical collection My_Project_History
  - Note: inside the service container, your host ./data is mounted as /data

Option B - Host CLI
```
python3 rag_ingest.py
```
Use a custom logical collection:
```
LOGICAL_COLLECTION=Team_Wiki python3 rag_ingest.py
```

Option C - Direct API
```
curl -s -X POST http://localhost:8000/v1/ingest/scan \
  -H 'Content-Type: application/json' \
  -d '{
        "base_dir": "/data/raw",
        "pattern": "**/*",
        "logical_collection": "My_Project_History"
      }' | jq
```

Re-ingesting a file replaces its prior chunks (idempotent by source_id).

## Search + rerank

In Open WebUI chats
- Enable Tools for the chat. If your model supports tool/function calling, set Tools policy to Auto.
- Use "Pivot RAG Search" - it embeds your query, searches Milvus (Top-K=25), reranks with bge-reranker-v2-m3, and injects the context.

Direct API
```
curl -s -X POST http://localhost:8000/v1/retrieval/search \
  -H 'Content-Type: application/json' \
  -d '{
        "query": "What did we decide about our VPN setup?",
        "top_k": 25,
        "logical_collection": "My_Project_History"
      }' | jq '.results[:5]'
```

## Open WebUI specifics in PIVOT
- Ingestion inside WebUI is disabled: DOC_PROCESSING_TYPE=none
- Extensions enabled: ENABLE_EXTENSIONS=true
- Custom extension "Pivot RAG Context Tool" provides two tools:
  - Pivot RAG Search - fetches reranked context from the service
  - Pivot RAG Ingest Scan - triggers server-side ingestion of /data/raw
- The extension contacts the RAG service via Docker DNS: http://rag-service:8000

If tools do not appear, restart WebUI:
```
sudo docker compose -f docker-compose.yml -f docker-compose.override.yml restart open-webui
```

## Configuration (env)
RAG service defaults:
- MILVUS_URI=http://milvus:19530
- EMBEDDING_MODEL=BAAI/bge-large-en
- RERANKER_MODEL=BAAI/bge-reranker-v2-m3
- CHUNK_SIZE=2048
- CHUNK_OVERLAP=200
- DEFAULT_LOGICAL_COLLECTION=My_Project_History

Open WebUI (override):
- ENABLE_EXTENSIONS=true
- DOC_PROCESSING_TYPE=none
- PIVOT_RAG_BASE_URL=http://rag-service:8000
- PIVOT_RAG_LOGICAL_COLLECTION=My_Project_History

Milvus/index (code defaults): HNSW(IP) M=16, efConstruction=200; search ef=128; Top-K=25 then rerank.

## Troubleshooting
- First run is slow - models download inside the RAG service container.
- Health shows milvus=false - wait for Milvus or check: sudo docker compose logs milvus
- Extension missing - verify files under openwebui/extensions/pivot_rag/ and restart WebUI.
- Tools do not auto-invoke - enable Tools and set policy to Auto with a tool-capable model; manual runs always work.
- Ingest finds 0 files - ensure host files are in ./data/raw; the service scans /data/raw inside the container.

### Git push errors: symbolic links and large cache files
If you see errors like:

- warning: unable to access 'openwebui/cache/.../.gitattributes': Too many levels of symbolic links
- RPC failed; HTTP 500 ... send-pack: unexpected disconnect while reading sideband packet

This is due to large runtime/model cache directories that were accidentally tracked. The repository now includes a .gitignore to exclude these paths (openwebui/cache, ollama/models, ollama/history, data/raw, milvus/*, openwebui/webui.db, logs, etc.). To clean files that are already tracked in your local index, run the following from the repo root:

```
sudo git pull --rebase

# Remove previously tracked runtime/cache data from the index (not your disk)
sudo git rm -r --cached \
  openwebui/cache \
  ollama/models \
  ollama/history \
  data/raw \
  milvus/db \
  milvus/etcd \
  milvus/minio \
  openwebui/webui.db

# Also clean generic LOGs that may have been tracked
sudo git rm -r --cached $(git ls-files | grep -E '(^|/)LOG(\.old.*)?$' || true)

# Commit the index cleanup and the new .gitignore
sudo git add .
sudo git commit -m "chore(vcs): ignore runtime caches, data/raw, and DB/logs; fix push errors"

# Try pushing again (large packs should be gone)
sudo git push
```

Notes:
- The data/raw directory is preserved in Git via an empty .gitkeep so the folder exists for clones, but your actual raw files remain untracked.
- Models and caches are re-created/downloaded at runtime by the services (Ollama, RAG service, Open WebUI) and do not need to be in Git.

## Notes
- Milvus schema fields: vector(1024), source_id, source_path, doc_title, mime_type, chunk_index, created_at, hash, logical_collection, text
- Embeddings are L2 normalized; Milvus uses IP metric (cosine-equivalent on normalized vectors)

## License
Provided as-is for internal use. Add your preferred license if redistributing.