"""
Embedding model management with caching.
"""

import os

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

from .config import EMBEDDING_MODEL, get_embeddings_cache, set_embeddings_cache
from .utils import timing_context


def get_embeddings(model_name: str = EMBEDDING_MODEL, device: str = "cpu", force_reload: bool = False):
    """
    Load embedding model (cached after first load).
    Uses FastEmbed only.
    
    Args:
        model_name: Name of the embedding model
        device: Kept for backward compatibility (ignored for FastEmbed)
        force_reload: If True, reload even if cached
        
    Returns:
        Embeddings instance (cached) - FastEmbedEmbeddings
    """
    cached = get_embeddings_cache()
    
    if cached is not None and not force_reload:
        return cached
    
    try:
        from langchain_community.embeddings import FastEmbedEmbeddings
        print(f"🧠 Using FastEmbedEmbeddings: {model_name} (fast, no PyTorch)")
        with timing_context("Loading FastEmbed model"):
            embeddings = FastEmbedEmbeddings(model_name=model_name)
        set_embeddings_cache(embeddings)
        print(f"   ✓ FastEmbed loaded and cached (will reuse on subsequent calls)")
        return embeddings
    except Exception as e:
        raise RuntimeError(
            "FastEmbed initialization failed. HuggingFace embeddings fallback has been removed."
        ) from e

