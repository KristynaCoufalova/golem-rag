"""
FemCAD Enhanced RAG - Custom Retriever with Azure OpenAI
Basics are always retrieved (not hardcoded in prompt)
Includes robust filtering for corrupted documents in vector DB

PERFORMANCE OPTIMIZATION:
All expensive operations are cached globally and reused across queries:
- Embedding model (BAAI/bge-base-en-v1.5): Loaded once, cached in memory
- Vector databases (Chroma): Opened once, cached connections
- BM25 indexes: Built once from all documents, cached in memory

This eliminates 30-60+ seconds of startup time per query.
The first call to build_enhanced_chain() will be slow (initialization),
but subsequent calls reuse cached resources and are nearly instant.
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

import argparse
from typing import List
from dotenv import load_dotenv

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    print("⚠️  tiktoken not available - token counting disabled. Install with: pip install tiktoken")

from langchain_chroma import Chroma

try:
    from .bm25_utils import extract_all_documents_from_chroma, build_bm25_retriever_from_chroma
except ImportError:
    try:
        from bm25_utils import extract_all_documents_from_chroma, build_bm25_retriever_from_chroma
    except ImportError:
        raise ImportError("Could not import bm25_utils. Please ensure bm25_utils.py exists in the same directory.")

try:
    from .conversation_memory import memory, EnhancedPrompt
except ImportError:
    try:
        from conversation_memory import memory, EnhancedPrompt
    except ImportError:
        memory = None

# Import from refactored modules
try:
    from .config import (
        CODE_DB_PATH, DOCS_DB_PATH, EMBEDDING_MODEL, PROJECT_ROOT,
        get_last_formatted_context_tokens
    )
except ImportError:
    from config import (
        CODE_DB_PATH, DOCS_DB_PATH, EMBEDDING_MODEL, PROJECT_ROOT,
        get_last_formatted_context_tokens
    )

try:
    from .chain_builder import build_enhanced_chain, invoke_chain_safe
except ImportError:
    from chain_builder import build_enhanced_chain, invoke_chain_safe

try:
    from .embeddings import get_embeddings
except ImportError:
    from embeddings import get_embeddings

try:
    from .formatters import SYSTEM_PROMPT, format_docs
except ImportError:
    from formatters import SYSTEM_PROMPT, format_docs

try:
    from .utils import count_tokens, format_token_count, timing_context
except ImportError:
    from utils import count_tokens, format_token_count, timing_context

# Re-export for backward compatibility
__all__ = [
    'build_enhanced_chain',
    'invoke_chain_safe',
    'format_docs',
    'SYSTEM_PROMPT',
    'CODE_DB_PATH',
    'DOCS_DB_PATH',
    'EMBEDDING_MODEL',
    'PROJECT_ROOT',
]


# ===== TEST/VERIFICATION: BM25 Infrastructure =====
def test_bm25_infrastructure(
    code_db_path: str = CODE_DB_PATH,
    docs_db_path: str = DOCS_DB_PATH,
    emb_model: str = EMBEDDING_MODEL,
    device: str = "cpu",
    test_queries: List[str] = None
):
    """
    Test and verify BM25 infrastructure is working correctly.
    
    This function:
    1. Loads Chroma vectorstores
    2. Extracts all documents
    3. Builds BM25 indices
    4. Tests retrieval with sample queries
    
    Args:
        code_db_path: Path to code vector database
        docs_db_path: Path to docs vector database
        emb_model: Embedding model name
        device: Device for embeddings
        test_queries: Optional list of test queries (defaults to common ones)
    """
    if test_queries is None:
        test_queries = [
            "how to create a beam",
            "cross section",
            "error handling",
            "Fcs.Beam"
        ]
    
    print("\n" + "=" * 80)
    print("🧪 Testing BM25 Infrastructure")
    print("=" * 80)
    
    # Load embeddings
    embeddings = get_embeddings(emb_model, device)
    
    # Test CODE database
    print(f"\n📦 Testing CODE database: {code_db_path}")
    if not os.path.exists(code_db_path):
        print(f"   ❌ CODE DB not found at: {code_db_path}")
        code_vectordb = None
    else:
        try:
            code_vectordb = Chroma(
                persist_directory=code_db_path,
                collection_name="code_rag",
                embedding_function=embeddings,
            )
            
            # Extract documents
            print("   📥 Extracting documents from CODE DB...")
            code_docs = extract_all_documents_from_chroma(code_vectordb)
            print(f"   ✓ Extracted {len(code_docs)} documents")
            
            if code_docs:
                # Build BM25
                print("   🔤 Building BM25 index...")
                bm25_code = build_bm25_retriever_from_chroma(code_vectordb, "CODE")
                
                if bm25_code:
                    # Test retrieval
                    print("   🧪 Testing BM25 retrieval...")
                    for query in test_queries[:2]:  # Test first 2 queries
                        results = bm25_code.invoke(query)
                        print(f"      Query: '{query}' → {len(results)} results")
                        if results:
                            preview = results[0].page_content[:80].replace("\n", " ")
                            print(f"         Top result: {preview}...")
                    print("   ✅ CODE BM25 infrastructure working!")
                else:
                    print("   ❌ Failed to build CODE BM25 index")
            else:
                print("   ⚠️ No documents found in CODE DB")
                
        except Exception as e:
            print(f"   ❌ Error testing CODE DB: {e}")
            import traceback
            traceback.print_exc()
            code_vectordb = None
    
    # Test DOCS database
    print(f"\n📦 Testing DOCS database: {docs_db_path}")
    if not os.path.exists(docs_db_path):
        print(f"   ❌ DOCS DB not found at: {docs_db_path}")
        docs_vectordb = None
    else:
        try:
            docs_vectordb = Chroma(
                persist_directory=docs_db_path,
                collection_name="docs_rag",
                embedding_function=embeddings,
            )
            
            # Extract documents
            print("   📥 Extracting documents from DOCS DB...")
            docs_docs = extract_all_documents_from_chroma(docs_vectordb)
            print(f"   ✓ Extracted {len(docs_docs)} documents")
            
            if docs_docs:
                # Build BM25
                print("   🔤 Building BM25 index...")
                bm25_docs = build_bm25_retriever_from_chroma(docs_vectordb, "DOCS")
                
                if bm25_docs:
                    # Test retrieval
                    print("   🧪 Testing BM25 retrieval...")
                    for query in test_queries[:2]:  # Test first 2 queries
                        results = bm25_docs.invoke(query)
                        print(f"      Query: '{query}' → {len(results)} results")
                        if results:
                            preview = results[0].page_content[:80].replace("\n", " ")
                            print(f"         Top result: {preview}...")
                    print("   ✅ DOCS BM25 infrastructure working!")
                else:
                    print("   ❌ Failed to build DOCS BM25 index")
            else:
                print("   ⚠️ No documents found in DOCS DB")
                
        except Exception as e:
            print(f"   ❌ Error testing DOCS DB: {e}")
            import traceback
            traceback.print_exc()
            docs_vectordb = None
    
    print("\n" + "=" * 80)
    print("✨ BM25 Infrastructure Test Complete")
    print("=" * 80 + "\n")


# ===== MAIN =====
def main():
    load_dotenv(PROJECT_ROOT / '.env')
    
    parser = argparse.ArgumentParser(
        description="FemCAD Enhanced RAG - Custom Retriever with Azure OpenAI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backend/rag/rag.py -q "how do I create a beam?"
  python backend/rag/rag.py -q "show me gblock examples" --k_code 3
  python backend/rag/rag.py -q "naming conventions" --show_retrieval
        """
    )
    
    parser.add_argument("-q", "--query", required=False, 
                       help="Query to ask (not required if --test_bm25 is used)")
    parser.add_argument("--code_db", default=CODE_DB_PATH)
    parser.add_argument("--docs_db", default=DOCS_DB_PATH)
    parser.add_argument("--basics", default=None)
    parser.add_argument("--emb_model", default=EMBEDDING_MODEL)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--deployment", default="gpt-5-mini")
    parser.add_argument("--k_docs", type=int, default=0)
    parser.add_argument("--k_code", type=int, default=3)
    parser.add_argument("--show_retrieval", action="store_true")
    parser.add_argument("--session_id", default=None)
    parser.add_argument("--disable_memory", action="store_true")
    parser.add_argument("--test_bm25", action="store_true", 
                       help="Test BM25 infrastructure instead of running a query")
    parser.add_argument("--rebuild_bm25", action="store_true",
                       help="Force rebuild BM25 indices (ignores disk cache)")
    
    args = parser.parse_args()
    
    # Handle test mode
    if args.test_bm25:
        load_dotenv(PROJECT_ROOT / '.env')
        test_bm25_infrastructure(
            code_db_path=args.code_db,
            docs_db_path=args.docs_db,
            emb_model=args.emb_model,
            device=args.device,
        )
        return 0
    
    # Query is required for normal operation
    if not args.query:
        parser.error("--query is required (or use --test_bm25 to test infrastructure)")
    
    print("\n" + "=" * 80)
    print("🔧 FemCAD ENHANCED Assistant (Azure OpenAI)")
    print("=" * 80)
    
    try:
        chain, retriever, _llm, _prompt = build_enhanced_chain(
            code_db_path=args.code_db,
            docs_db_path=args.docs_db,
            basics_path=args.basics,
            emb_model=args.emb_model,
            device=args.device,
            azure_deployment=args.deployment,
            k_docs=args.k_docs,
            k_code=args.k_code,
            force_reload=args.rebuild_bm25
        )
        
        memory_enabled = not args.disable_memory and memory is not None
        session_id = args.session_id
        if memory_enabled:
            with timing_context("Memory operations (build enhanced prompt)"):
                session_id = session_id or memory.create_session()
                enhanced_prompt = memory.build_enhanced_prompt(session_id, args.query)
            print(f"🧠 Conversation memory active (session: {session_id})")
            if enhanced_prompt.retrieval_query != args.query:
                print(f"📝 Query enhanced: '{args.query}' → '{enhanced_prompt.retrieval_query}'")
        else:
            # Create EnhancedPrompt with no enhancement when memory is disabled
            try:
                from .conversation_memory import EnhancedPrompt
            except ImportError:
                try:
                    from conversation_memory import EnhancedPrompt
                except ImportError:
                    # Fallback if EnhancedPrompt import failed
                    from dataclasses import dataclass
                    @dataclass
                    class FallbackEnhancedPrompt:
                        retrieval_query: str
                        context: str
                        original_question: str
                    EnhancedPrompt = FallbackEnhancedPrompt
            enhanced_prompt = EnhancedPrompt(
                retrieval_query=args.query,
                context="",
                original_question=args.query
            )
            if args.disable_memory:
                print("ℹ️ Conversation memory disabled via --disable_memory")
            else:
                print("⚠️ Conversation memory unavailable (module import failed)")
                if args.session_id:
                    print("   (Provided session_id is ignored without memory)")
        
        retrieval_query = enhanced_prompt.retrieval_query
        history_context = enhanced_prompt.context
        
        if args.show_retrieval:
            print(f"🔍 Retrieving for: '{retrieval_query}'\n")
            docs = retriever.invoke(retrieval_query)
            print(f"Retrieved {len(docs)} documents:")
            for i, d in enumerate(docs, 1):
                doc_type = d.metadata.get("type", "retrieved")
                src = d.metadata.get("source", "unknown")
                preview = d.page_content[:80].replace("\n", " ")
                print(f"  {i}. [{doc_type}] {src}")
                print(f"     {preview}...")
            print()
        
        print(f"❓ Your Question: {args.query}\n")
        if enhanced_prompt.retrieval_query != args.query:
            print(f"🔄 Query enhanced for retrieval:")
            print(f"   Original: {args.query}")
            print(f"   Enhanced: {enhanced_prompt.retrieval_query}")
            history = memory.get_history(session_id, max_turns=2) if memory_enabled else []
            if history:
                print(f"   Context from: {len(history)} previous turn(s)\n")
            else:
                print()
        if history_context:
            print("🧾 Conversation context provided to model:")
            # Show preview of context
            preview_lines = history_context.split("\n")[:4]
            for line in preview_lines:
                if line.strip():
                    print(f"   {line[:70]}..." if len(line) > 70 else f"   {line}")
            if len(history_context.split("\n")) > 4:
                print("   ...")
            print()
        print("🔍 Processing...")
        
        # Count input tokens (before LLM call)
        if TIKTOKEN_AVAILABLE:
            system_tokens = count_tokens(SYSTEM_PROMPT)
            question_tokens = count_tokens(enhanced_prompt.retrieval_query)
            history_tokens = count_tokens(history_context) if history_context else 0
            # Note: Context tokens will be shown by format_docs function
        
        # Time the overall query processing (includes retrieval + formatting + LLM)
        import time
        query_start = time.time()
        
        # The chain invocation includes: retrieval -> format_docs -> LLM
        # Individual retrieval timings are shown in the retriever
        # Token counts for retrieved context are shown in format_docs
        answer = invoke_chain_safe(
            chain,
            question=enhanced_prompt.retrieval_query,
            history=history_context,
            retrieval_query=retrieval_query,
        )
        
        query_elapsed = time.time() - query_start
        
        # Calculate and display full token breakdown
        if TIKTOKEN_AVAILABLE:
            context_tokens = get_last_formatted_context_tokens()
            # Human message template overhead (approximate)
            template_overhead = count_tokens("Conversation context:\n\n\nQuestion: \n\nAvailable Knowledge:\n")
            
            total_input_tokens = system_tokens + question_tokens + history_tokens + context_tokens + template_overhead
            
            print(f"   📊 Complete token breakdown:")
            print(f"      System prompt: {format_token_count(system_tokens)} tokens")
            if history_tokens > 0:
                print(f"      History: {format_token_count(history_tokens)} tokens")
            print(f"      Question: {format_token_count(question_tokens)} tokens")
            print(f"      Context (formatted): {format_token_count(context_tokens)} tokens")
            print(f"      Template overhead: {format_token_count(template_overhead)} tokens")
            print(f"      📊 TOTAL INPUT TOKENS: {format_token_count(total_input_tokens)} tokens")
            
            output_tokens = count_tokens(answer)
            total_tokens = total_input_tokens + output_tokens
            print(f"      Output: {format_token_count(output_tokens)} tokens")
            print(f"      📊 TOTAL TOKENS (input + output): {format_token_count(total_tokens)} tokens")
        
        print(f"   ⏱️  LLM generation (includes formatting): {query_elapsed:.2f}s")
        
        if memory_enabled and session_id:
            with timing_context("Saving to memory", verbose=False):
                memory.add_turn(session_id, args.query, answer)
            print(f"🆔 Session ID: {session_id}")
        
        print("\n" + "=" * 80)
        print("💡 ANSWER")
        print("=" * 80)
        print(answer.strip())
        print("=" * 80)
        
        print("\n✅ Query completed!\n")
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Please ensure:")
        print(f"  1. Vector DBs exist")
        print(f"  2. Basics file exists")
        print(f"  3. Run: python build_dual_vectordb.py (to rebuild clean DBs)")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
