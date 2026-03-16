"""
Code chunking strategies.

Chunks code by:
- Functions/classes (preferred)
- Fixed-size blocks with overlap (fallback)
"""

import re
from typing import List, Dict, Optional
from langchain_core.documents import Document


class CodeChunker:
    """
    Chunker for code files.
    
    Prefers semantic boundaries (functions, classes) over fixed-size chunks.
    Falls back to fixed-size chunking if semantic boundaries can't be detected.
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        prefer_semantic: bool = True
    ):
        """
        Initialize code chunker.
        
        Args:
            chunk_size: Maximum chunk size in characters (fallback)
            chunk_overlap: Overlap between chunks in characters (fallback)
            prefer_semantic: Whether to prefer semantic boundaries (default: True)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.prefer_semantic = prefer_semantic
    
    def _detect_language(self, content: str, path: str) -> str:
        """Detect programming language from content or path."""
        # From path
        if path.endswith(".py"):
            return "python"
        elif path.endswith(".ts") or path.endswith(".tsx"):
            return "typescript"
        elif path.endswith(".js") or path.endswith(".jsx"):
            return "javascript"
        elif path.endswith(".cs"):
            return "csharp"
        elif path.endswith(".java"):
            return "java"
        elif path.endswith(".go"):
            return "go"
        elif path.endswith(".rs"):
            return "rust"
        elif path.endswith(".cpp") or path.endswith(".cc") or path.endswith(".cxx"):
            return "cpp"
        elif path.endswith(".c"):
            return "c"
        else:
            return "unknown"
    
    def _chunk_by_functions_python(self, content: str) -> List[Dict[str, any]]:
        """Chunk Python code by functions and classes."""
        chunks = []
        lines = content.split("\n")
        
        current_chunk = []
        current_start_line = 0
        in_function = False
        indent_level = 0
        
        for i, line in enumerate(lines, 1):
            # Detect function or class definition
            func_match = re.match(r'^(\s*)(def|class)\s+(\w+)', line)
            
            if func_match:
                # Save previous chunk if exists
                if current_chunk and in_function:
                    chunk_text = "\n".join(current_chunk)
                    if chunk_text.strip():
                        chunks.append({
                            "content": chunk_text,
                            "line_start": current_start_line,
                            "line_end": i - 1
                        })
                
                # Start new chunk
                current_chunk = [line]
                current_start_line = i
                in_function = True
                indent_level = len(func_match.group(1))
            
            elif in_function:
                # Check if we're still in the same function/class
                if line.strip():
                    line_indent = len(line) - len(line.lstrip())
                    # If indent decreased significantly, we might be out
                    if line_indent < indent_level and line.strip() and not line.strip().startswith("#"):
                        # End of function/class
                        chunk_text = "\n".join(current_chunk)
                        if chunk_text.strip():
                            chunks.append({
                                "content": chunk_text,
                                "line_start": current_start_line,
                                "line_end": i - 1
                            })
                        current_chunk = []
                        in_function = False
                    else:
                        current_chunk.append(line)
                else:
                    current_chunk.append(line)
        
        # Add last chunk
        if current_chunk and in_function:
            chunk_text = "\n".join(current_chunk)
            if chunk_text.strip():
                chunks.append({
                    "content": chunk_text,
                    "line_start": current_start_line,
                    "line_end": len(lines)
                })
        
        return chunks
    
    def _chunk_by_functions_typescript(self, content: str) -> List[Dict[str, any]]:
        """Chunk TypeScript/JavaScript code by functions and classes."""
        chunks = []
        lines = content.split("\n")
        
        current_chunk = []
        current_start_line = 0
        in_block = False
        brace_count = 0
        
        for i, line in enumerate(lines, 1):
            # Detect function or class definition
            func_match = re.match(r'^\s*(export\s+)?(async\s+)?(function|class|const|let|var)\s+(\w+)', line)
            
            if func_match:
                # Save previous chunk if exists
                if current_chunk and in_block and brace_count == 0:
                    chunk_text = "\n".join(current_chunk)
                    if chunk_text.strip():
                        chunks.append({
                            "content": chunk_text,
                            "line_start": current_start_line,
                            "line_end": i - 1
                        })
                
                # Start new chunk
                current_chunk = [line]
                current_start_line = i
                in_block = True
                brace_count = line.count("{") - line.count("}")
            
            elif in_block:
                brace_count += line.count("{") - line.count("}")
                current_chunk.append(line)
                
                # End of block
                if brace_count == 0 and line.strip().endswith("}"):
                    chunk_text = "\n".join(current_chunk)
                    if chunk_text.strip():
                        chunks.append({
                            "content": chunk_text,
                            "line_start": current_start_line,
                            "line_end": i
                        })
                    current_chunk = []
                    in_block = False
        
        # Add last chunk
        if current_chunk and in_block:
            chunk_text = "\n".join(current_chunk)
            if chunk_text.strip():
                chunks.append({
                    "content": chunk_text,
                    "line_start": current_start_line,
                    "line_end": len(lines)
                })
        
        return chunks
    
    def _chunk_fixed_size(self, content: str, start_line: int = 1) -> List[Dict[str, any]]:
        """Fallback: chunk by fixed size with overlap."""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", " ", ""]
        )
        
        chunks = splitter.split_text(content)
        
        # Calculate line numbers (approximate)
        result = []
        current_line = start_line
        for chunk in chunks:
            lines_in_chunk = chunk.count("\n") + 1
            result.append({
                "content": chunk,
                "line_start": current_line,
                "line_end": current_line + lines_in_chunk - 1
            })
            current_line += lines_in_chunk - self.chunk_overlap // 50  # Approximate overlap
        
        return result
    
    def chunk(
        self,
        content: str,
        path: str,
        metadata: Optional[Dict] = None
    ) -> List[Document]:
        """
        Chunk code content into documents.
        
        Args:
            content: Code content as string
            path: File path (for language detection)
            metadata: Base metadata to add to all chunks
        
        Returns:
            List of Document objects
        """
        if metadata is None:
            metadata = {}
        
        language = self._detect_language(content, path)
        
        chunks = []
        
        # Try semantic chunking first
        if self.prefer_semantic:
            if language == "python":
                semantic_chunks = self._chunk_by_functions_python(content)
            elif language in ["typescript", "javascript"]:
                semantic_chunks = self._chunk_by_functions_typescript(content)
            else:
                semantic_chunks = []
            
            # Use semantic chunks if we found any
            if semantic_chunks:
                chunks = semantic_chunks
            else:
                # Fallback to fixed-size
                chunks = self._chunk_fixed_size(content)
        else:
            # Direct fixed-size chunking
            chunks = self._chunk_fixed_size(content)
        
        # Convert to Documents
        documents = []
        for i, chunk_info in enumerate(chunks):
            chunk_metadata = {
                **metadata,
                "path": path,
                "language": language,
                "chunk_index": i,
                "line_start": chunk_info["line_start"],
                "line_end": chunk_info["line_end"],
                "chunk_type": "code"
            }
            
            documents.append(Document(
                page_content=chunk_info["content"],
                metadata=chunk_metadata
            ))
        
        return documents
