"""
Utility functions for timing and token counting.
"""

import time
from contextlib import contextmanager
from typing import Optional

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    print("⚠️  tiktoken not available - token counting disabled. Install with: pip install tiktoken")


# ===== TIMING UTILITIES =====
@contextmanager
def timing_context(step_name: str, verbose: bool = True):
    """Context manager to time operations"""
    start = time.time()
    if verbose:
        print(f"   ⏱️  Starting: {step_name}...")
    try:
        yield
    finally:
        elapsed = time.time() - start
        if verbose:
            print(f"   ⏱️  {step_name}: {elapsed:.2f}s")


# ===== TOKEN COUNTING UTILITIES =====
_tokenizer_cache: Optional[object] = None


def get_tokenizer():
    """Get tiktoken tokenizer (cached)"""
    global _tokenizer_cache
    if not TIKTOKEN_AVAILABLE:
        return None
    
    if _tokenizer_cache is None:
        # Use cl100k_base encoding (GPT-4, GPT-3.5-turbo, and newer models)
        # This should work for Azure OpenAI deployments
        try:
            _tokenizer_cache = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            print(f"   ⚠️  Could not initialize tokenizer: {e}")
            return None
    
    return _tokenizer_cache


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken"""
    if not TIKTOKEN_AVAILABLE:
        return 0
    
    tokenizer = get_tokenizer()
    if tokenizer is None:
        return 0
    
    try:
        return len(tokenizer.encode(text))
    except Exception:
        # Fallback: rough estimate (1 token ≈ 4 characters)
        return len(text) // 4


def format_token_count(count: int) -> str:
    """Format token count with K/M suffixes"""
    if count >= 1000000:
        return f"{count / 1000000:.1f}M"
    elif count >= 1000:
        return f"{count / 1000:.1f}K"
    else:
        return str(count)

