"""
Configuration constants and global caches for FemCAD RAG system.
"""

import os
from pathlib import Path
from typing import Any, Optional

# CRITICAL: Set these BEFORE any PyTorch/transformers imports to avoid macOS mutex issues
# These must be set at module import time, not just in the function
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("KMP_INIT_AT_FORK", "FALSE")
os.environ.setdefault("KMP_AFFINITY", "disabled")
os.environ.setdefault("OMP_PROC_BIND", "false")
# Additional macOS-specific workarounds
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever

# ===== PATHS =====
# Standalone repo: rag/ is the package dir, parent is repo root
BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent

CODE_DB_PATH = os.getenv("FEMCAD_CODE_DB", str(PROJECT_ROOT / "vectordb_code"))
DOCS_DB_PATH = os.getenv("FEMCAD_DOCS_DB", str(PROJECT_ROOT / "vectordb_docs"))
EMBEDDING_MODEL = os.getenv("FEMCAD_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")

# BM25 cache directory (stores pickled BM25 retrievers)
BM25_CACHE_DIR = PROJECT_ROOT / ".bm25_cache"
BM25_CACHE_DIR.mkdir(exist_ok=True)

# BM25 cache file paths
BM25_CODE_CACHE_PATH = BM25_CACHE_DIR / "bm25_code.pkl"
BM25_DOCS_CACHE_PATH = BM25_CACHE_DIR / "bm25_docs.pkl"

# ===== GLOBAL CACHES (loaded once, reused across all queries) =====
_embeddings_cache: Optional[Any] = None
_code_vectordb_cache: Optional[Chroma] = None
_docs_vectordb_cache: Optional[Chroma] = None
_bm25_code_cache: Optional[BM25Retriever] = None
_bm25_docs_cache: Optional[BM25Retriever] = None
_basics_doc_cache: Optional[Document] = None

# Token tracking (per query)
_last_formatted_context_tokens: int = 0


def get_embeddings_cache() -> Optional[Any]:
    """Get the cached embeddings model."""
    return _embeddings_cache


def set_embeddings_cache(value: Optional[Any]):
    """Set the cached embeddings model."""
    global _embeddings_cache
    _embeddings_cache = value


def get_code_vectordb_cache() -> Optional[Chroma]:
    """Get the cached code vectorstore."""
    return _code_vectordb_cache


def set_code_vectordb_cache(value: Optional[Chroma]):
    """Set the cached code vectorstore."""
    global _code_vectordb_cache
    _code_vectordb_cache = value


def get_docs_vectordb_cache() -> Optional[Chroma]:
    """Get the cached docs vectorstore."""
    return _docs_vectordb_cache


def set_docs_vectordb_cache(value: Optional[Chroma]):
    """Set the cached docs vectorstore."""
    global _docs_vectordb_cache
    _docs_vectordb_cache = value


def get_bm25_code_cache() -> Optional[BM25Retriever]:
    """Get the cached BM25 code retriever."""
    return _bm25_code_cache


def set_bm25_code_cache(value: Optional[BM25Retriever]):
    """Set the cached BM25 code retriever."""
    global _bm25_code_cache
    _bm25_code_cache = value


def get_bm25_docs_cache() -> Optional[BM25Retriever]:
    """Get the cached BM25 docs retriever."""
    return _bm25_docs_cache


def set_bm25_docs_cache(value: Optional[BM25Retriever]):
    """Set the cached BM25 docs retriever."""
    global _bm25_docs_cache
    _bm25_docs_cache = value


def get_basics_doc_cache() -> Optional[Document]:
    """Get the cached basics document."""
    return _basics_doc_cache


def set_basics_doc_cache(value: Optional[Document]):
    """Set the cached basics document."""
    global _basics_doc_cache
    _basics_doc_cache = value


def get_last_formatted_context_tokens() -> int:
    """Get the last formatted context token count."""
    return _last_formatted_context_tokens


def set_last_formatted_context_tokens(value: int):
    """Set the last formatted context token count."""
    global _last_formatted_context_tokens
    _last_formatted_context_tokens = value


# ===== CLOUD VECTOR DB CONFIGURATION =====
# Vector DB mode: "local" (ChromaDB) or "cloud" (Qdrant/pgvector)
VECTOR_DB_MODE = os.getenv("VECTOR_DB_MODE", "local").lower()

# Cloud provider: "qdrant" or "pgvector" (only used when mode="cloud")
VECTOR_DB_PROVIDER = os.getenv("VECTOR_DB_PROVIDER", "chroma").lower()

# Qdrant configuration (for cloud mode with provider="qdrant")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_LOCATION = os.getenv("QDRANT_LOCATION")  # For local Qdrant

# pgvector configuration (for cloud mode with provider="pgvector")
PGVECTOR_CONNECTION_STRING = os.getenv("PGVECTOR_CONNECTION_STRING")
PGVECTOR_TABLE_NAME = os.getenv("PGVECTOR_TABLE_NAME", "embeddings")

# Collections/namespaces
VECTOR_DB_COLLECTIONS = os.getenv("VECTOR_DB_COLLECTIONS", "femcad-code,femcad-docs").split(",")

# Fallback mechanism
VECTOR_DB_FALLBACK_TO_LOCAL = os.getenv("VECTOR_DB_FALLBACK_TO_LOCAL", "false").lower() == "true"

# Embedding versioning
EMBEDDING_MODEL_VERSION = os.getenv("EMBEDDING_MODEL_VERSION", "1.0")

# State persistence (for incremental updates)
RAG_STATE_STORAGE = os.getenv("RAG_STATE_STORAGE", "file")  # file | postgres | s3
RAG_STATE_PATH = os.getenv("RAG_STATE_PATH", str(PROJECT_ROOT / "rag_state.json"))

