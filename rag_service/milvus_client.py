from __future__ import annotations

import time
from typing import List, Dict, Any, Optional

from pymilvus import (
    connections,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
    utility,
)

from . import config


VECTOR_FIELD = "vector"


class MilvusManager:
    def __init__(self, uri: str | None = None, token: str | None = None, db_name: str | None = None):
        self.uri = uri or config.MILVUS_URI
        self.token = token or config.MILVUS_TOKEN or None
        self.db_name = db_name or config.MILVUS_DB_NAME or None
        # Establish connection
        connections.connect(alias="default", uri=self.uri, token=self.token, db_name=self.db_name)
        self.collection_name = config.MILVUS_COLLECTION
        self._collection: Optional[Collection] = None
        self.ensure_collection()

    def ensure_collection(self):
        if utility.has_collection(self.collection_name):
            self._collection = Collection(self.collection_name)
            try:
                # ensure index loaded
                self._collection.load()
            except Exception:
                pass
            return

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name=VECTOR_FIELD, dtype=DataType.FLOAT_VECTOR, dim=1024),
            FieldSchema(name="source_id", dtype=DataType.VARCHAR, max_length=config.SOURCE_ID_MAX_LEN),
            FieldSchema(name="source_path", dtype=DataType.VARCHAR, max_length=config.SOURCE_PATH_MAX_LEN),
            FieldSchema(name="doc_title", dtype=DataType.VARCHAR, max_length=config.TITLE_MAX_LEN),
            FieldSchema(name="mime_type", dtype=DataType.VARCHAR, max_length=config.MIME_MAX_LEN),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="created_at", dtype=DataType.INT64),
            FieldSchema(name="hash", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="logical_collection", dtype=DataType.VARCHAR, max_length=config.COLLECTION_FIELD_MAX_LEN),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=config.TEXT_MAX_LEN),
        ]
        schema = CollectionSchema(fields=fields, description="Pivot RAG documents")
        coll = Collection(self.collection_name, schema)

        # Create HNSW index over vector field with IP metric
        index_params = {"index_type": "HNSW", "metric_type": "IP", "params": {"M": 16, "efConstruction": 200}}
        coll.create_index(field_name=VECTOR_FIELD, index_params=index_params)
        coll.load()
        self._collection = coll

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            self.ensure_collection()
        return self._collection

    def delete_by_source_id(self, source_id: str, logical_collection: str):
        expr = f'source_id == "{source_id}" and logical_collection == "{logical_collection}"'
        self.collection.delete(expr)

    def upsert_chunks(self, items: List[Dict[str, Any]]):
        if not items:
            return
        # Prepare columnar data
        vectors = [it["vector"] for it in items]
        source_id = [it["source_id"] for it in items]
        source_path = [it.get("source_path", "") for it in items]
        doc_title = [it.get("doc_title", "") for it in items]
        mime_type = [it.get("mime_type", "") for it in items]
        chunk_index = [int(it.get("chunk_index", 0)) for it in items]
        created_at = [int(it.get("created_at", int(time.time()))) for it in items]
        hash_vals = [it.get("hash", "") for it in items]
        logical_collection = [it.get("logical_collection", config.DEFAULT_LOGICAL_COLLECTION) for it in items]
        texts = [it.get("text", "") for it in items]

        entities = [
            vectors,
            source_id,
            source_path,
            doc_title,
            mime_type,
            chunk_index,
            created_at,
            hash_vals,
            logical_collection,
            texts,
        ]
        self.collection.insert(entities)
        self.collection.flush()

    def search(self, query_vector: List[float], top_k: int = 25, logical_collection: Optional[str] = None, expr: Optional[str] = None, output_fields: Optional[List[str]] = None):
        if output_fields is None:
            output_fields = [
                "source_id",
                "source_path",
                "doc_title",
                "mime_type",
                "chunk_index",
                "created_at",
                "hash",
                "logical_collection",
                "text",
            ]
        base_expr = None
        if logical_collection:
            base_expr = f'logical_collection == "{logical_collection}"'
        if expr:
            base_expr = f"({base_expr}) and ({expr})" if base_expr else expr

        # Search params for HNSW
        params = {"metric_type": "IP", "params": {"ef": 128}}
        res = self.collection.search(
            data=[query_vector],
            anns_field=VECTOR_FIELD,
            param=params,
            limit=top_k,
            expr=base_expr,
            output_fields=output_fields,
        )
        return res[0] if res else []
