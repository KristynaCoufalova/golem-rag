"""
Embedding model management with caching.
"""

import os
from typing import Optional

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

from langchain_huggingface import HuggingFaceEmbeddings

from .config import EMBEDDING_MODEL, get_embeddings_cache, set_embeddings_cache
from .utils import timing_context


def get_embeddings(model_name: str = EMBEDDING_MODEL, device: str = "cpu", force_reload: bool = False):
    """
    Load embedding model (cached after first load).
    
    Priority: FastEmbed (if installed, avoids PyTorch) -> HuggingFace (sentence-transformers)
    
    Args:
        model_name: Name of the embedding model
        device: Device to run on (cpu/cuda) - ignored for FastEmbed
        force_reload: If True, reload even if cached
        
    Returns:
        Embeddings instance (cached) - FastEmbedEmbeddings or HuggingFaceEmbeddings
    """
    cached = get_embeddings_cache()
    
    if cached is not None and not force_reload:
        return cached
    
    # Try FastEmbed first (lightweight, no PyTorch, avoids macOS mutex issues)
    try:
        from langchain_community.embeddings import FastEmbedEmbeddings
        print(f"🧠 Using FastEmbedEmbeddings: {model_name} (fast, no PyTorch)")
        with timing_context("Loading FastEmbed model"):
            embeddings = FastEmbedEmbeddings(model_name=model_name)
        set_embeddings_cache(embeddings)
        print(f"   ✓ FastEmbed loaded and cached (will reuse on subsequent calls)")
        return embeddings
    except Exception as e:
        print(f"   ⚠️  FastEmbed not available ({e}), falling back to HuggingFace")
    
    # Fallback: HuggingFace sentence-transformers (requires PyTorch)
    # Ensure environment variables are set (already set at module level, but enforce here too)
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    os.environ["KMP_INIT_AT_FORK"] = "FALSE"
    os.environ["KMP_AFFINITY"] = "disabled"
    os.environ["OMP_PROC_BIND"] = "false"
    
    print(f"🧠 Loading HuggingFace embeddings: {model_name} (device={device})")
    print(f"   (OpenMP workarounds active: OMP_NUM_THREADS=1, TOKENIZERS_PARALLELISM=false)")
    with timing_context("Loading HuggingFace embedding model"):
        embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
        )
    set_embeddings_cache(embeddings)
    print(f"   ✓ HuggingFace embeddings cached (will reuse on subsequent calls)")
    return embeddings

