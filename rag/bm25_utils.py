"""
BM25 Utilities for Hybrid RAG Retrieval

This module provides utilities for building and using BM25 (lexical) retrievers
as a complement to dense (embedding-based) retrieval in the RAG system.

Includes disk caching to avoid rebuilding BM25 indices on every run.
"""

import os
import pickle
from pathlib import Path
from typing import List, Optional, Dict, Any
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever


def extract_all_documents_from_chroma(vectordb: Chroma) -> List[Document]:
    """
    Extract all documents from a Chroma vectorstore for BM25 indexing.
    
    This function retrieves all documents stored in the Chroma database,
    which are needed to build BM25 indices.
    
    Args:
        vectordb: Chroma vectorstore instance
        
    Returns:
        List of Document objects with page_content and metadata
        
    Raises:
        Exception: If extraction fails
    """
    try:
        # Get all documents - Chroma's get() without filters returns all
        # We need to handle the case where there might be many documents
        raw_data = vectordb.get()
        
        documents = raw_data.get("documents", [])
        metadatas = raw_data.get("metadatas", [])
        ids = raw_data.get("ids", [])
        
        # Validate we have data
        if not documents:
            return []
        
        # Ensure metadatas list matches documents length
        if len(metadatas) != len(documents):
            # Pad with empty dicts if needed
            metadatas = metadatas + [{}] * (len(documents) - len(metadatas))
        
        # Build Document objects
        docs: List[Document] = []
        for i, (text, meta) in enumerate(zip(documents, metadatas)):
            # Filter out invalid documents
            if not text or not isinstance(text, str) or not text.strip():
                continue
            
            # Ensure metadata is a dict
            if not isinstance(meta, dict):
                meta = {}
            
            # Add ID to metadata if available
            if i < len(ids):
                meta["_chroma_id"] = ids[i]
            
            docs.append(Document(page_content=text, metadata=meta))
        
        return docs
        
    except Exception as e:
        raise Exception(f"Failed to extract documents from Chroma: {e}")


def _get_chroma_db_mtime(vectordb: Chroma, db_path: Optional[str] = None) -> Optional[float]:
    """
    Get the modification time of the Chroma database.
    
    Args:
        vectordb: Chroma vectorstore instance
        db_path: Optional path to the database directory (if known)
        
    Returns:
        Modification time as float, or None if cannot determine
    """
    try:
        # Try provided path first
        if db_path:
            db_file = Path(db_path) / "chroma.sqlite3"
            if db_file.exists():
                return db_file.stat().st_mtime
        
        # Try to get from vectordb internals (fragile but works for persisted DBs)
        try:
            persist_dir = getattr(vectordb._client, '_persist_directory', None)
            if persist_dir:
                db_file = Path(persist_dir) / "chroma.sqlite3"
                if db_file.exists():
                    return db_file.stat().st_mtime
        except (AttributeError, TypeError):
            pass
        
        return None
    except Exception:
        return None


def _get_chroma_doc_count(vectordb: Chroma, raw_data: Optional[Dict[str, Any]] = None) -> int:
    """
    Get the number of documents in the Chroma database.
    
    Args:
        vectordb: Chroma vectorstore instance
        raw_data: Optional pre-fetched data from vectordb.get() to avoid duplicate calls
        
    Returns:
        Number of documents
    """
    try:
        if raw_data is None:
            raw_data = vectordb.get()
        documents = raw_data.get("documents", [])
        return len(documents)
    except Exception:
        return 0


def save_bm25_cache(
    bm25_retriever: BM25Retriever,
    cache_path: Path,
    vectordb: Chroma,
    retriever_name: str,
    db_path: Optional[str] = None
) -> bool:
    """
    Save BM25 retriever to disk cache with metadata.
    
    Args:
        bm25_retriever: BM25Retriever instance to save
        cache_path: Path where to save the cache file
        vectordb: Chroma vectorstore instance (for metadata)
        retriever_name: Name for logging
        db_path: Optional path to the database directory (if known)
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Create cache directory if it doesn't exist
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get metadata about the source database
        db_mtime = _get_chroma_db_mtime(vectordb, db_path)
        doc_count = _get_chroma_doc_count(vectordb)
        
        # Try to get persist_dir from vectordb or use provided db_path
        persist_dir = db_path
        if not persist_dir:
            try:
                persist_dir = getattr(vectordb._client, '_persist_directory', None)
            except (AttributeError, TypeError):
                pass
        
        metadata = {
            "db_path": str(persist_dir) if persist_dir else None,
            "db_mtime": db_mtime,
            "doc_count": doc_count,
            "retriever_name": retriever_name,
        }
        
        # Save both the retriever and metadata
        cache_data = {
            "retriever": bm25_retriever,
            "metadata": metadata,
        }
        
        with open(cache_path, "wb") as f:
            pickle.dump(cache_data, f)
        
        return True
    except Exception as e:
        print(f"   ⚠️ Failed to save BM25 cache for {retriever_name}: {e}")
        return False


def load_bm25_cache(
    cache_path: Path,
    vectordb: Chroma,
    retriever_name: str,
    db_path: Optional[str] = None
) -> Optional[BM25Retriever]:
    """
    Load BM25 retriever from disk cache if it's still valid.
    
    Checks if the source Chroma database has changed by comparing:
    - Database modification time
    - Document count
    
    Args:
        cache_path: Path to the cache file
        vectordb: Chroma vectorstore instance (for validation)
        retriever_name: Name for logging
        db_path: Optional path to the database directory (if known)
        
    Returns:
        BM25Retriever instance if cache is valid, None otherwise
    """
    try:
        if not cache_path.exists():
            return None
        
        # Load cache
        with open(cache_path, "rb") as f:
            cache_data = pickle.load(f)
        
        retriever = cache_data.get("retriever")
        metadata = cache_data.get("metadata", {})
        
        if not retriever:
            return None
        
        # Validate cache is still valid
        # Check mtime first (cheaper - no DB query)
        current_db_mtime = _get_chroma_db_mtime(vectordb, db_path)
        cached_db_mtime = metadata.get("db_mtime")
        
        if cached_db_mtime is not None and current_db_mtime is not None:
            if abs(current_db_mtime - cached_db_mtime) > 1.0:  # Allow 1 second tolerance
                print(f"   🔄 BM25 cache for {retriever_name} invalidated (DB modified)")
                return None
        
        # Only check doc count if mtime check passed (avoids unnecessary vectordb.get() if mtime already invalidated)
        cached_doc_count = metadata.get("doc_count")
        if cached_doc_count is not None:
            # Fetch once and reuse for doc count check
            try:
                raw_data = vectordb.get()
                current_doc_count = len(raw_data.get("documents", []))
            except Exception:
                current_doc_count = _get_chroma_doc_count(vectordb)
            
            if current_doc_count != cached_doc_count:
                print(f"   🔄 BM25 cache for {retriever_name} invalidated (doc count changed: {cached_doc_count} → {current_doc_count})")
                return None
        
        print(f"   ✓ Loaded BM25 {retriever_name} from cache ({cached_doc_count} docs)")
        return retriever
        
    except Exception as e:
        print(f"   ⚠️ Failed to load BM25 cache for {retriever_name}: {e}")
        return None


def build_bm25_retriever_from_chroma(
    vectordb: Chroma, 
    retriever_name: str = "unknown",
    cache_path: Optional[Path] = None,
    force_rebuild: bool = False,
    db_path: Optional[str] = None
) -> Optional[BM25Retriever]:
    """
    Build a BM25 retriever from all documents in a Chroma vectorstore.
    
    Optionally uses disk cache to avoid rebuilding on every run.
    
    Args:
        vectordb: Chroma vectorstore instance
        retriever_name: Name for logging (e.g., "CODE" or "DOCS")
        cache_path: Optional path to cache file. If None, no caching is used.
        force_rebuild: If True, rebuild even if cache exists
        db_path: Optional path to the database directory (for cache validation)
        
    Returns:
        BM25Retriever instance or None if building fails
    """
    # Try to load from cache first
    if cache_path and not force_rebuild:
        cached = load_bm25_cache(cache_path, vectordb, retriever_name, db_path)
        if cached is not None:
            return cached
    
    # Build from scratch
    print(f"   🔤 Building BM25 retriever for {retriever_name}")
    try:
        # Extract all documents
        docs = extract_all_documents_from_chroma(vectordb)
        
        if not docs:
            print(f"   ⚠️ No valid {retriever_name} docs found for BM25")
            return None
        
        # Build BM25 index
        bm25_retriever = BM25Retriever.from_documents(docs)
        print(f"   ✓ BM25 {retriever_name} index built with {len(docs)} docs")
        
        # Save to cache if path provided
        if cache_path:
            if save_bm25_cache(bm25_retriever, cache_path, vectordb, retriever_name, db_path):
                print(f"   💾 BM25 {retriever_name} cache saved")
        
        return bm25_retriever
        
    except Exception as e:
        print(f"   ⚠️ Failed to build BM25 for {retriever_name}: {e}")
        import traceback
        traceback.print_exc()
        return None

