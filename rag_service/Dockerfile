FROM python:3.11-slim

# System deps for PyMuPDF (fitz)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgl1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/rag_service

EXPOSE 8000

ENV MILVUS_URI=http://milvus:19530 \
    EMBEDDING_MODEL=BAAI/bge-large-en \
    RERANKER_MODEL=BAAI/bge-reranker-v2-m3 \
    CHUNK_SIZE=2048 \
    CHUNK_OVERLAP=200 \
    DEFAULT_LOGICAL_COLLECTION=My_Project_History

CMD ["uvicorn", "rag_service.app:app", "--host", "0.0.0.0", "--port", "8000"]
