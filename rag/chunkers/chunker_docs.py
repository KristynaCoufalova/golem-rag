"""
Documentation chunking strategies.

Chunks documentation by:
- Headings (##, ###)
- Paragraphs
- Fixed-size with overlap (fallback)
"""

from typing import List, Dict, Optional
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class DocsChunker:
    """
    Chunker for documentation files (Markdown, etc.).
    
    Prefers semantic boundaries (headings, paragraphs) over fixed-size chunks.
    """
    
    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        prefer_semantic: bool = True
    ):
        """
        Initialize docs chunker.
        
        Args:
            chunk_size: Maximum chunk size in characters
            chunk_overlap: Overlap between chunks in characters
            prefer_semantic: Whether to prefer semantic boundaries (default: True)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.prefer_semantic = prefer_semantic
        
        # Text splitter with markdown-aware separators
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""]
        )
    
    def _chunk_by_headings(self, content: str) -> List[Dict[str, any]]:
        """Chunk by markdown headings."""
        import re
        
        chunks = []
        lines = content.split("\n")
        
        current_chunk = []
        current_start_line = 0
        current_heading = None
        
        for i, line in enumerate(lines, 1):
            # Detect heading
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if heading_match:
                # Save previous chunk if exists
                if current_chunk:
                    chunk_text = "\n".join(current_chunk)
                    if chunk_text.strip():
                        chunks.append({
                            "content": chunk_text,
                            "line_start": current_start_line,
                            "line_end": i - 1,
                            "heading": current_heading
                        })
                
                # Start new chunk
                current_chunk = [line]
                current_start_line = i
                current_heading = heading_match.group(2).strip()
            else:
                current_chunk.append(line)
        
        # Add last chunk
        if current_chunk:
            chunk_text = "\n".join(current_chunk)
            if chunk_text.strip():
                chunks.append({
                    "content": chunk_text,
                    "line_start": current_start_line,
                    "line_end": len(lines),
                    "heading": current_heading
                })
        
        return chunks
    
    def chunk(
        self,
        content: str,
        path: str,
        metadata: Optional[Dict] = None
    ) -> List[Document]:
        """
        Chunk documentation content into documents.
        
        Args:
            content: Documentation content as string
            path: File path
            metadata: Base metadata to add to all chunks
        
        Returns:
            List of Document objects
        """
        if metadata is None:
            metadata = {}
        
        chunks = []
        
        # Try semantic chunking first
        if self.prefer_semantic:
            semantic_chunks = self._chunk_by_headings(content)
            
            # Use semantic chunks if we found any meaningful ones
            if semantic_chunks and len(semantic_chunks) > 1:
                chunks = semantic_chunks
            else:
                # Fallback to text splitter
                chunk_texts = self.splitter.split_text(content)
                # Approximate line numbers
                current_line = 1
                for chunk_text in chunk_texts:
                    lines_in_chunk = chunk_text.count("\n") + 1
                    chunks.append({
                        "content": chunk_text,
                        "line_start": current_line,
                        "line_end": current_line + lines_in_chunk - 1
                    })
                    current_line += lines_in_chunk - self.chunk_overlap // 50
        else:
            # Direct text splitter
            chunk_texts = self.splitter.split_text(content)
            current_line = 1
            for chunk_text in chunk_texts:
                lines_in_chunk = chunk_text.count("\n") + 1
                chunks.append({
                    "content": chunk_text,
                    "line_start": current_line,
                    "line_end": current_line + lines_in_chunk - 1
                })
                current_line += lines_in_chunk - self.chunk_overlap // 50
        
        # Convert to Documents
        documents = []
        for i, chunk_info in enumerate(chunks):
            chunk_metadata = {
                **metadata,
                "path": path,
                "chunk_index": i,
                "line_start": chunk_info["line_start"],
                "line_end": chunk_info["line_end"],
                "chunk_type": "documentation"
            }
            
            if "heading" in chunk_info:
                chunk_metadata["heading"] = chunk_info["heading"]
            
            documents.append(Document(
                page_content=chunk_info["content"],
                metadata=chunk_metadata
            ))
        
        return documents
