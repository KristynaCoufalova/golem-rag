"""
Lightweight fallback engine for FemCAD Web UI.

Provides basic retrieval functionality when the enhanced RAG chain
is unavailable (e.g., missing dependencies, configuration issues).
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SimpleDocument:
    """Simple document representation for fallback engine."""
    page_content: str
    metadata: dict


class SimpleFallbackEngine:
    """
    Extremely lightweight retrieval that keeps FemCAD UI usable offline.
    
    Uses simple token-based matching instead of embeddings or vector search.
    Suitable for development/testing when full RAG infrastructure isn't available.
    """

    def __init__(
        self,
        project_root: Path,
        basics_path: Path,
        docs_dir: Path,
        k_docs: int = 0,
    ) -> None:
        """
        Initialize the fallback engine.
        
        Args:
            project_root: Root directory of the project
            basics_path: Path to the FemCAD basics markdown file
            docs_dir: Directory containing documentation markdown files
            k_docs: Number of documentation snippets to retrieve
        """
        self.project_root = Path(project_root)
        self.basics_doc = self._load_basics(basics_path)
        self.k_docs = max(0, k_docs)
        self.snippets = self._load_docs(docs_dir)
        if not self.snippets:
            logger.warning(
                "No documentation snippets found in %s; fallback will serve basics only.",
                docs_dir,
            )

    def run(self, question: str, k_docs: Optional[int] = None) -> tuple[str, List[SimpleDocument]]:
        """
        Run a query and return answer with documents.
        
        Args:
            question: User's question
            k_docs: Number of docs to retrieve (defaults to self.k_docs)
            
        Returns:
            Tuple of (answer_text, list_of_documents)
        """
        effective_k_docs = self.k_docs if k_docs is None else max(0, k_docs)
        docs = self._retrieve(question, effective_k_docs)
        answer = self._compose_answer(question, docs)
        return answer, docs

    def _load_basics(self, basics_path: Path) -> SimpleDocument:
        """Load the FemCAD basics document. Uses placeholder if file is missing (e.g. on Azure without data)."""
        if not basics_path.exists():
            logger.warning("FemCAD basics not found at %s; using placeholder.", basics_path)
            return SimpleDocument(
                page_content="FemCAD fundamentals data is not available in this environment.",
                metadata={
                    "source": "placeholder",
                    "type": "always_included",
                    "path": "",
                },
            )
        text = basics_path.read_text(encoding="utf-8")
        return SimpleDocument(
            page_content=text,
            metadata={
                "source": basics_path.name,
                "type": "always_included",
                "path": str(basics_path.relative_to(self.project_root)),
            },
        )

    def _load_docs(self, docs_dir: Path) -> List[dict]:
        """Load and chunk documentation files. Returns empty list if dir missing (e.g. on Azure without data)."""
        if not docs_dir.exists():
            logger.warning("Documentation directory missing: %s", docs_dir)
            return []

        snippets: List[dict] = []
        for path in sorted(docs_dir.rglob("*.md")):
            try:
                raw = path.read_text(encoding="utf-8", errors="ignore")
                for chunk in self._chunk_text(raw):
                    tokens = self._tokenize(chunk)
                    if len(tokens) < 3:
                        continue
                    snippets.append(
                        {
                            "doc": SimpleDocument(
                                page_content=chunk.strip(),
                                metadata={
                                    "source": path.stem.replace("_", " ").title(),
                                    "type": "documentation",
                                    "path": str(path.relative_to(self.project_root)),
                                },
                            ),
                            "tokens": tokens,
                        }
                    )
            except Exception as e:
                # Skip files that can't be read
                print(f"⚠️  Warning: Could not load {path}: {e}")
                continue
        return snippets

    def _retrieve(self, question: str, k_docs: int) -> List[SimpleDocument]:
        """
        Retrieve relevant documents using token overlap matching.
        
        Args:
            question: Query string
            k_docs: Number of documents to retrieve
            
        Returns:
            List of documents (basics + top matching docs)
        """
        tokens = self._tokenize(question)
        matches: List[tuple[float, SimpleDocument]] = []
        for snippet in self.snippets:
            overlap = len(tokens & snippet["tokens"])
            if not overlap:
                continue
            # Simple scoring: coverage (how much of query matches) + density (how much of doc matches)
            coverage = overlap / (len(tokens) or 1)
            density = overlap / len(snippet["tokens"])
            score = (coverage * 0.7) + (density * 0.3)
            matches.append((score, snippet["doc"]))

        matches.sort(key=lambda item: item[0], reverse=True)
        top_docs = [doc for _, doc in matches[:k_docs]]
        if not top_docs:
            # Fall back to first snippets to avoid empty responses
            top_docs = [snippet["doc"] for snippet in self.snippets[:k_docs]]
        return [self.basics_doc, *top_docs]

    @staticmethod
    def _chunk_text(text: str, min_chars: int = 320) -> Iterable[str]:
        """
        Chunk text into paragraphs of minimum size.
        
        Args:
            text: Text to chunk
            min_chars: Minimum characters per chunk
            
        Yields:
            Text chunks
        """
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        buffer: List[str] = []
        count = 0
        for para in paragraphs:
            buffer.append(para)
            count += len(para)
            if count >= min_chars:
                yield "\n\n".join(buffer)
                buffer = []
                count = 0
        if buffer:
            yield "\n\n".join(buffer)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """
        Simple tokenization: extract words of 3+ characters.
        
        Args:
            text: Text to tokenize
            
        Returns:
            Set of lowercase tokens
        """
        return set(re.findall(r"[a-z0-9]{3,}", text.lower()))

    def _compose_answer(self, question: str, docs: List[SimpleDocument]) -> str:
        """
        Compose a simple answer from retrieved documents.
        
        Args:
            question: User's question
            docs: Retrieved documents
            
        Returns:
            Answer text
        """
        if len(docs) <= 1:
            return (
                "FemCAD fundamentals loaded, but no matching documentation snippets were found. "
                "Try asking with more concrete FemCAD keywords."
            )

        highlights = []
        for doc in docs[1:]:  # Skip basics (first doc)
            snippet = " ".join(line.strip() for line in doc.page_content.splitlines()[:4])
            snippet = snippet[:400].rstrip()
            highlights.append(f"- {doc.metadata.get('source', 'documentation')}: {snippet}")

        preamble = (
            "Using the local FemCAD fundamentals and documentation, here are the most relevant notes "
            f"for '{question}':"
        )
        return f"{preamble}\n" + "\n".join(highlights) + "\n\nRefer to the full context below for details."

