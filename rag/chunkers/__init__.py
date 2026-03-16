"""
Chunking modules for different content types.

- chunker_code.py: Code chunking (functions, classes, blocks)
- chunker_docs.py: Documentation chunking (paragraphs, headings)
"""

from .chunker_code import CodeChunker
from .chunker_docs import DocsChunker

__all__ = ["CodeChunker", "DocsChunker"]
