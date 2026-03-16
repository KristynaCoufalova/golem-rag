"""
Custom retriever for FemCAD RAG system with hybrid dense + lexical retrieval.
Includes Reciprocal Rank Fusion (RRF) and optional cross-encoder reranking.
"""

import time
from typing import List, Optional, Dict

from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_community.retrievers import BM25Retriever

from .utils import count_tokens, format_token_count

# Lazy-loaded cross-encoder for reranking
_cross_encoder = None


def _get_cross_encoder():
    """Lazy-load cross-encoder model (downloaded once, ~80MB)."""
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            print("   ✓ Cross-encoder reranker loaded (ms-marco-MiniLM-L-6-v2)")
        except Exception as e:
            print(f"   ⚠️  Cross-encoder not available, skipping reranking: {e}")
            _cross_encoder = False  # sentinel to avoid retrying
    return _cross_encoder if _cross_encoder is not False else None


class FemCADEnhancedRetriever(BaseRetriever):
    """
    Custom retriever that ALWAYS includes FemCAD basics,
    then adds relevant docs and code examples.
    Hybrid: dense + lexical (BM25) with RRF fusion and cross-encoder reranking.
    Filters out invalid documents with None content.
    """

    basics_doc: Document
    docs_retriever: BaseRetriever           # dense docs
    code_retriever: BaseRetriever           # dense code
    bm25_docs_retriever: Optional[BM25Retriever] = None
    bm25_code_retriever: Optional[BM25Retriever] = None
    k_docs: int = 0
    k_code: int = 3
    k_bm25_docs: int = 0
    k_bm25_code: int = 3
    enable_reranking: bool = True
    rrf_k: int = 60  # RRF constant (standard default)
    
    def _safe_retrieve(self, retriever: BaseRetriever, query: str, k: int, source_name: str) -> List[Document]:
        """Safely retrieve documents with robust error handling"""
        try:
            # Try to get documents
            raw_docs = retriever.invoke(query)
            
            # Filter out invalid documents
            valid_docs = []
            for doc in raw_docs:
                try:
                    # Check if document is valid
                    if (doc.page_content is not None 
                        and isinstance(doc.page_content, str) 
                        and doc.page_content.strip()):
                        valid_docs.append(doc)
                except Exception as e:
                    # Skip documents that cause errors
                    continue
            
            # Limit to requested amount
            valid_docs = valid_docs[:k]
            
            # Report filtering
            invalid_count = len(raw_docs) - len(valid_docs)
            if invalid_count > 0:
                print(f"   ⚠️  Filtered out {invalid_count} invalid doc(s) from {source_name}")
            
            return valid_docs
            
        except Exception as e:
            print(f"   ⚠️  Error retrieving from {source_name}: {e}")
            return []
    
    def _doc_key(self, d: Document) -> tuple:
        """Generate a dedup key for a document using position metadata when available."""
        meta = d.metadata or {}
        source = meta.get("source", "")
        path = meta.get("path", "")
        # Prefer chunk_index for identity (exact chunk position in the source)
        if "chunk_index" in meta:
            return (source, path, "ci", meta["chunk_index"])
        # Fall back to line_start if available (handles overlapping chunks)
        if "line_start" in meta:
            return (source, path, "ls", meta["line_start"])
        # Last resort: content prefix
        return (source, path, "txt", d.page_content[:80] if isinstance(d.page_content, str) else "")

    def _is_overlapping(self, a: Document, b: Document) -> bool:
        """Check if two chunks from the same source overlap significantly."""
        ma, mb = a.metadata or {}, b.metadata or {}
        # Must be from the same source file
        if ma.get("source", "") != mb.get("source", "") or ma.get("path", "") != mb.get("path", ""):
            return False
        # Adjacent chunk indices overlap by design (chunk_overlap in splitter)
        if "chunk_index" in ma and "chunk_index" in mb:
            return abs(ma["chunk_index"] - mb["chunk_index"]) <= 1
        return False

    def _dedup(self, docs: List[Document]) -> List[Document]:
        """Deduplicate by identity key and remove chunks that overlap with higher-ranked ones."""
        seen_keys = set()
        unique = []
        for d in docs:
            key = self._doc_key(d)
            if key in seen_keys:
                continue
            # Check if this chunk overlaps with an already-accepted higher-ranked chunk
            if any(self._is_overlapping(d, accepted) for accepted in unique):
                continue
            seen_keys.add(key)
            unique.append(d)
        return unique

    def _rrf_merge(
        self,
        dense_docs: List[Document],
        bm25_docs: List[Document],
        k: int,
    ) -> List[Document]:
        """
        Reciprocal Rank Fusion: merge two ranked lists into one.
        RRF score = sum( 1 / (rrf_k + rank) ) across lists where doc appears.
        """
        if not bm25_docs:
            return dense_docs[:k]
        if not dense_docs:
            return bm25_docs[:k]

        scores: Dict[tuple, float] = {}
        doc_map: Dict[tuple, Document] = {}

        for rank, d in enumerate(dense_docs):
            key = self._doc_key(d)
            scores[key] = scores.get(key, 0.0) + 1.0 / (self.rrf_k + rank + 1)
            doc_map[key] = d

        for rank, d in enumerate(bm25_docs):
            key = self._doc_key(d)
            scores[key] = scores.get(key, 0.0) + 1.0 / (self.rrf_k + rank + 1)
            if key not in doc_map:
                doc_map[key] = d

        sorted_keys = sorted(scores.keys(), key=lambda key: scores[key], reverse=True)
        return [doc_map[key] for key in sorted_keys[:k]]

    def _rerank(self, query: str, docs: List[Document], top_k: int) -> List[Document]:
        """Rerank documents using cross-encoder. Falls back to original order if unavailable."""
        if not docs or len(docs) <= 1:
            return docs

        cross_encoder = _get_cross_encoder()
        if cross_encoder is None:
            return docs[:top_k]

        try:
            start = time.time()
            pairs = [(query, d.page_content) for d in docs]
            scores = cross_encoder.predict(pairs)
            ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
            elapsed = time.time() - start
            print(f"   ⏱️  Reranking {len(docs)} docs: {elapsed:.2f}s")
            return [d for _, d in ranked[:top_k]]
        except Exception as e:
            print(f"   ⚠️  Reranking failed, using RRF order: {e}")
            return docs[:top_k]

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        """Hybrid retrieval: basics + RRF(dense, BM25) + reranking (docs + code)"""

        # 1. ALWAYS include basics first
        results: List[Document] = [self.basics_doc]

        # --- DOCS: dense + BM25 with RRF ---
        docs_dense: List[Document] = []
        docs_lex: List[Document] = []
        if self.k_docs > 0:
            start = time.time()
            docs_dense = self._safe_retrieve(
                self.docs_retriever, query, self.k_docs * 2, "docs DB (dense)"
            )
            elapsed = time.time() - start
            print(f"   ⏱️  DOCS dense retrieval: {elapsed:.2f}s")
        if self.k_bm25_docs > 0 and self.bm25_docs_retriever is not None:
            try:
                start = time.time()
                raw_bm25_docs = self.bm25_docs_retriever.invoke(query)
                elapsed = time.time() - start
                print(f"   ⏱️  DOCS BM25 retrieval: {elapsed:.2f}s")
                docs_lex = [
                    d for d in raw_bm25_docs
                    if d.page_content and isinstance(d.page_content, str) and d.page_content.strip()
                ][: self.k_bm25_docs * 2]
            except Exception as e:
                print(f"   ⚠️  Error retrieving from docs BM25: {e}")
                docs_lex = []
        # RRF merge instead of simple concatenation
        docs_fused = self._dedup(self._rrf_merge(docs_dense, docs_lex, k=max(self.k_docs, self.k_bm25_docs) * 2))
        # Rerank the fused results
        if self.enable_reranking and docs_fused:
            docs_combined = self._rerank(query, docs_fused, top_k=self.k_docs)
        else:
            docs_combined = docs_fused[:self.k_docs]
        docs_tokens = sum(count_tokens(d.page_content) for d in docs_combined if d.page_content)
        print(f"   📚 Docs dense={len(docs_dense)}, bm25={len(docs_lex)}, fused={len(docs_fused)}, final={len(docs_combined)} ({format_token_count(docs_tokens)} tokens)")
        results.extend(docs_combined)

        # --- CODE: dense + BM25 with RRF ---
        code_dense: List[Document] = []
        code_lex: List[Document] = []
        if self.k_code > 0:
            start = time.time()
            code_dense = self._safe_retrieve(
                self.code_retriever, query, self.k_code * 2, "code DB (dense)"
            )
            elapsed = time.time() - start
            print(f"   ⏱️  CODE dense retrieval: {elapsed:.2f}s")
        if self.k_bm25_code > 0 and self.bm25_code_retriever is not None:
            try:
                start = time.time()
                raw_bm25_code = self.bm25_code_retriever.invoke(query)
                elapsed = time.time() - start
                print(f"   ⏱️  CODE BM25 retrieval: {elapsed:.2f}s")
                code_lex = [
                    d for d in raw_bm25_code
                    if d.page_content and isinstance(d.page_content, str) and d.page_content.strip()
                ][: self.k_bm25_code * 2]
            except Exception as e:
                print(f"   ⚠️  Error retrieving from code BM25: {e}")
                code_lex = []
        # RRF merge instead of simple concatenation
        code_fused = self._dedup(self._rrf_merge(code_dense, code_lex, k=max(self.k_code, self.k_bm25_code) * 2))
        # Rerank the fused results
        if self.enable_reranking and code_fused:
            code_combined = self._rerank(query, code_fused, top_k=self.k_code)
        else:
            code_combined = code_fused[:self.k_code]
        code_tokens = sum(count_tokens(d.page_content) for d in code_combined if d.page_content)
        print(f"   💻 Code dense={len(code_dense)}, bm25={len(code_lex)}, fused={len(code_fused)}, final={len(code_combined)} ({format_token_count(code_tokens)} tokens)")
        results.extend(code_combined)

        # Count basics tokens
        basics_tokens = count_tokens(self.basics_doc.page_content) if self.basics_doc.page_content else 0
        total_retrieved_tokens = basics_tokens + docs_tokens + code_tokens
        print(f"   📊 Total retrieved context: {format_token_count(total_retrieved_tokens)} tokens (basics: {format_token_count(basics_tokens)}, docs: {format_token_count(docs_tokens)}, code: {format_token_count(code_tokens)})")

        return results

