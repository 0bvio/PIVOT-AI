import os


def env_str(key: str, default: str) -> str:
    return os.getenv(key, default)


def env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


# Models
EMBEDDING_MODEL = env_str("EMBEDDING_MODEL", "BAAI/bge-large-en")
RERANKER_MODEL = env_str("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

# Chunking
CHUNK_SIZE = env_int("CHUNK_SIZE", 2048)
CHUNK_OVERLAP = env_int("CHUNK_OVERLAP", 200)

# Milvus
MILVUS_URI = env_str("MILVUS_URI", "http://localhost:19530")
MILVUS_TOKEN = env_str("MILVUS_TOKEN", "")
MILVUS_DB_NAME = env_str("MILVUS_DB_NAME", "")  # use default

# Collections
DEFAULT_LOGICAL_COLLECTION = env_str("DEFAULT_LOGICAL_COLLECTION", "My_Project_History")
MILVUS_COLLECTION = env_str("MILVUS_COLLECTION", "pivot_docs_v1")

# Misc
TEXT_MAX_LEN = env_int("TEXT_MAX_LEN", 32768)
SOURCE_PATH_MAX_LEN = env_int("SOURCE_PATH_MAX_LEN", 1024)
TITLE_MAX_LEN = env_int("TITLE_MAX_LEN", 512)
COLLECTION_FIELD_MAX_LEN = env_int("COLLECTION_FIELD_MAX_LEN", 128)
MIME_MAX_LEN = env_int("MIME_MAX_LEN", 64)
SOURCE_ID_MAX_LEN = env_int("SOURCE_ID_MAX_LEN", 64)
