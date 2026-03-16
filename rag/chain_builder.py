"""
RAG chain builder with caching for expensive operations.
"""

import os
# CRITICAL: Set these BEFORE any PyTorch/transformers imports to avoid macOS mutex issues
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("KMP_INIT_AT_FORK", "FALSE")
os.environ.setdefault("KMP_AFFINITY", "disabled")
os.environ.setdefault("OMP_PROC_BIND", "false")

import time
from operator import itemgetter

from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel
from langchain_openai import AzureChatOpenAI

try:
    from .bm25_utils import build_bm25_retriever_from_chroma
except ImportError:
    try:
        from bm25_utils import build_bm25_retriever_from_chroma
    except ImportError:
        build_bm25_retriever_from_chroma = None

from .config import (
    CODE_DB_PATH, DOCS_DB_PATH, EMBEDDING_MODEL, PROJECT_ROOT,
    get_code_vectordb_cache, set_code_vectordb_cache,
    get_docs_vectordb_cache, set_docs_vectordb_cache,
    get_bm25_code_cache, set_bm25_code_cache,
    get_bm25_docs_cache, set_bm25_docs_cache,
    get_basics_doc_cache, set_basics_doc_cache,
    BM25_CODE_CACHE_PATH, BM25_DOCS_CACHE_PATH,
    VECTOR_DB_MODE,
)
from .vectorstore_factory import create_vectorstore
from .retriever import FemCADEnhancedRetriever
from .basics_loader import load_femcad_basics
from .embeddings import get_embeddings
from .formatters import format_docs, SYSTEM_PROMPT
from .utils import timing_context


def _build_bm25_from_cloud(vectordb, retriever_name: str):
    """
    Build a BM25 retriever from a cloud vectorstore by extracting documents
    via similarity_search with a broad query. This enables hybrid retrieval
    for cloud deployments.
    """
    try:
        from langchain_community.retrievers import BM25Retriever
        from langchain_core.documents import Document

        print(f"   🔤 Building BM25 for {retriever_name} from cloud vectorstore...")

        # Extract documents from cloud store using a broad similarity search
        # We use multiple generic queries to get good coverage
        all_docs = []
        seen_keys = set()
        sample_queries = ["code", "function", "example", "beam", "load", "structure", "element", "create"]

        for sq in sample_queries:
            try:
                results = vectordb.similarity_search(sq, k=200)
                for doc in results:
                    if not doc.page_content or not isinstance(doc.page_content, str) or not doc.page_content.strip():
                        continue
                    key = doc.page_content[:100]
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_docs.append(doc)
            except Exception:
                continue

        if not all_docs:
            print(f"   ⚠️  No documents extracted from cloud store for {retriever_name}")
            return None

        bm25_retriever = BM25Retriever.from_documents(all_docs)
        print(f"   ✓ BM25 {retriever_name} built from cloud with {len(all_docs)} docs")
        return bm25_retriever

    except Exception as e:
        print(f"   ⚠️  Failed to build cloud BM25 for {retriever_name}: {e}")
        return None


def build_enhanced_chain(
    code_db_path: str = CODE_DB_PATH,
    docs_db_path: str = DOCS_DB_PATH,
    basics_path: str = None,
    emb_model: str = EMBEDDING_MODEL,
    device: str = "cpu",
    azure_deployment: str = "gpt-5-mini",
    k_docs: int = 0,
    k_code: int = 3,
    force_reload: bool = False
):
    """
    Build enhanced RAG with custom retriever.
    
    All expensive operations (embeddings, vectorstores, BM25) are cached
    and reused across calls. Set force_reload=True to rebuild everything.
    """
    if basics_path is None:
        basics_path = str(PROJECT_ROOT / "data" / "femcad_basics_compact.md")
    
    init_start = time.time()
    
    print("\n" + "=" * 80)
    print("🚀 Building Enhanced FemCAD RAG (Custom Retriever)")
    print("=" * 80)
    print(f"📂 Project root: {PROJECT_ROOT}")
    
    # Load basics (cached)
    basics_doc_cache = get_basics_doc_cache()
    if basics_doc_cache is None or force_reload:
        print(f"\n📘 Loading FemCAD basics: {basics_path}")
        basics_doc = load_femcad_basics(basics_path)
        set_basics_doc_cache(basics_doc)
        print(f"   ✓ Basics cached")
    else:
        print(f"\n📘 Using cached FemCAD basics")
        basics_doc = basics_doc_cache
    
    # Load embeddings (cached)
    embeddings = get_embeddings(emb_model, device, force_reload=force_reload)
    
    # Load CODE vector DB (cached)
    code_vectordb_cache = get_code_vectordb_cache()
    if code_vectordb_cache is None or force_reload:
        print(f"\n📦 Loading CODE database")
        if VECTOR_DB_MODE == "cloud":
            # Use cloud database (PostgreSQL)
            print(f"   Mode: Cloud (PostgreSQL)")
            with timing_context("Loading CODE vectorstore from cloud"):
                code_vectordb = create_vectorstore(
                    mode="cloud",
                    collection_name="femcad-code-histruct",  # Your actual collection name
                    embedding_function=embeddings,
                )
        else:
            # Use local ChromaDB
            print(f"   Mode: Local (ChromaDB)")
            print(f"   Path: {code_db_path}")
            if not os.path.exists(code_db_path):
                raise FileNotFoundError(f"Code DB not found: {code_db_path}")
            
            with timing_context("Loading CODE vectorstore from local"):
                code_vectordb = Chroma(
                    persist_directory=code_db_path,
                    collection_name="code_rag",
                    embedding_function=embeddings,
                )
        set_code_vectordb_cache(code_vectordb)
        print(f"   ✓ CODE vectorstore cached")
    else:
        print(f"\n📦 Using cached CODE vectorstore")
        code_vectordb = code_vectordb_cache
    
    # Request more documents to account for filtering
    with timing_context("Creating CODE retriever"):
        # Handle both Chroma (local) and CloudVectorStore (cloud)
        if isinstance(code_vectordb, Chroma):
            code_retriever = code_vectordb.as_retriever(search_kwargs={"k": k_code * 3})
        else:
            # Cloud vectorstore - access underlying vectorstore for as_retriever
            from .cloud_vectorstore import CloudVectorStore
            if isinstance(code_vectordb, CloudVectorStore):
                code_retriever = code_vectordb._vectorstore.as_retriever(search_kwargs={"k": k_code * 3})
            else:
                # Fallback: try as_retriever directly
                code_retriever = code_vectordb.as_retriever(search_kwargs={"k": k_code * 3})
    print(f"   ✓ Will retrieve up to {k_code} valid code examples")
    
    # --- Build BM25 retriever for CODE (lexical layer) - CACHED (memory + disk) ---
    bm25_code_retriever = None
    if build_bm25_retriever_from_chroma is not None or VECTOR_DB_MODE == "cloud":
        bm25_code_cache = get_bm25_code_cache()
        if force_reload:
            print(f"\n🔤 Rebuilding BM25 index for CODE (--rebuild_bm25 flag)")
            with timing_context("Building BM25 CODE index"):
                if isinstance(code_vectordb, Chroma) and build_bm25_retriever_from_chroma is not None:
                    bm25_code_retriever = build_bm25_retriever_from_chroma(
                        code_vectordb,
                        "CODE",
                        cache_path=BM25_CODE_CACHE_PATH,
                        force_rebuild=True,
                        db_path=code_db_path
                    )
                elif VECTOR_DB_MODE == "cloud":
                    bm25_code_retriever = _build_bm25_from_cloud(code_vectordb, "CODE")
            set_bm25_code_cache(bm25_code_retriever)
            if bm25_code_retriever:
                print(f"   ✓ BM25 CODE index rebuilt and cached")
        elif bm25_code_cache is not None:
            print(f"\n🔤 Using cached BM25 CODE index (memory)")
            bm25_code_retriever = bm25_code_cache
        else:
            print(f"\n🔤 Loading BM25 index for CODE (checking cache...)")
            with timing_context("Loading BM25 CODE index"):
                if isinstance(code_vectordb, Chroma) and build_bm25_retriever_from_chroma is not None:
                    bm25_code_retriever = build_bm25_retriever_from_chroma(
                        code_vectordb,
                        "CODE",
                        cache_path=BM25_CODE_CACHE_PATH,
                        force_rebuild=False,
                        db_path=code_db_path
                    )
                elif VECTOR_DB_MODE == "cloud":
                    bm25_code_retriever = _build_bm25_from_cloud(code_vectordb, "CODE")
            set_bm25_code_cache(bm25_code_retriever)
            if bm25_code_retriever:
                print(f"   ✓ BM25 CODE index loaded and cached")
    
    # Load DOCS vector DB (cached)
    docs_vectordb_cache = get_docs_vectordb_cache()
    if docs_vectordb_cache is None or force_reload:
        print(f"\n📦 Loading DOCS database")
        if VECTOR_DB_MODE == "cloud":
            # Use cloud database (PostgreSQL)
            print(f"   Mode: Cloud (PostgreSQL)")
            with timing_context("Loading DOCS vectorstore from cloud"):
                # Try femcad-docs collection, fallback to docs_rag if not found
                try:
                    docs_vectordb = create_vectorstore(
                        mode="cloud",
                        collection_name="femcad-docs",  # Try this first
                        embedding_function=embeddings,
                    )
                except Exception:
                    # Fallback to docs_rag if femcad-docs doesn't exist
                    docs_vectordb = create_vectorstore(
                        mode="cloud",
                        collection_name="docs_rag",
                        embedding_function=embeddings,
                    )
        else:
            # Use local ChromaDB
            print(f"   Mode: Local (ChromaDB)")
            print(f"   Path: {docs_db_path}")
            if not os.path.exists(docs_db_path):
                raise FileNotFoundError(f"Docs DB not found: {docs_db_path}")
            
            with timing_context("Loading DOCS vectorstore from local"):
                docs_vectordb = Chroma(
                    persist_directory=docs_db_path,
                    collection_name="docs_rag",
                    embedding_function=embeddings,
                )
        set_docs_vectordb_cache(docs_vectordb)
        print(f"   ✓ DOCS vectorstore cached")
    else:
        print(f"\n📦 Using cached DOCS vectorstore")
        docs_vectordb = docs_vectordb_cache
    
    # Request more documents to account for filtering
    with timing_context("Creating DOCS retriever"):
        # Handle both Chroma (local) and CloudVectorStore (cloud)
        if isinstance(docs_vectordb, Chroma):
            docs_retriever = docs_vectordb.as_retriever(search_kwargs={"k": k_docs * 3})
        else:
            # Cloud vectorstore - access underlying vectorstore for as_retriever
            from .cloud_vectorstore import CloudVectorStore
            if isinstance(docs_vectordb, CloudVectorStore):
                docs_retriever = docs_vectordb._vectorstore.as_retriever(search_kwargs={"k": k_docs * 3})
            else:
                # Fallback: try as_retriever directly
                docs_retriever = docs_vectordb.as_retriever(search_kwargs={"k": k_docs * 3})
    print(f"   ✓ Will retrieve up to {k_docs} valid documentation snippets")
    
    # --- Build BM25 retriever for DOCS (lexical layer) - CACHED (memory + disk) ---
    bm25_docs_retriever = None
    if build_bm25_retriever_from_chroma is not None or VECTOR_DB_MODE == "cloud":
        bm25_docs_cache = get_bm25_docs_cache()
        if force_reload:
            print(f"\n🔤 Rebuilding BM25 index for DOCS (--rebuild_bm25 flag)")
            with timing_context("Building BM25 DOCS index"):
                if isinstance(docs_vectordb, Chroma) and build_bm25_retriever_from_chroma is not None:
                    bm25_docs_retriever = build_bm25_retriever_from_chroma(
                        docs_vectordb,
                        "DOCS",
                        cache_path=BM25_DOCS_CACHE_PATH,
                        force_rebuild=True,
                        db_path=docs_db_path
                    )
                elif VECTOR_DB_MODE == "cloud":
                    bm25_docs_retriever = _build_bm25_from_cloud(docs_vectordb, "DOCS")
            set_bm25_docs_cache(bm25_docs_retriever)
            if bm25_docs_retriever:
                print(f"   ✓ BM25 DOCS index rebuilt and cached")
        elif bm25_docs_cache is not None:
            print(f"\n🔤 Using cached BM25 DOCS index (memory)")
            bm25_docs_retriever = bm25_docs_cache
        else:
            print(f"\n🔤 Loading BM25 index for DOCS (checking cache...)")
            with timing_context("Loading BM25 DOCS index"):
                if isinstance(docs_vectordb, Chroma) and build_bm25_retriever_from_chroma is not None:
                    bm25_docs_retriever = build_bm25_retriever_from_chroma(
                        docs_vectordb,
                        "DOCS",
                        cache_path=BM25_DOCS_CACHE_PATH,
                        force_rebuild=False,
                        db_path=docs_db_path
                    )
                elif VECTOR_DB_MODE == "cloud":
                    bm25_docs_retriever = _build_bm25_from_cloud(docs_vectordb, "DOCS")
            set_bm25_docs_cache(bm25_docs_retriever)
            if bm25_docs_retriever:
                print(f"   ✓ BM25 DOCS index loaded and cached")
    
    # Create custom retriever
    print(f"\n🔧 Creating FemCAD Enhanced Retriever")
    enhanced_retriever = FemCADEnhancedRetriever(
        basics_doc=basics_doc,
        docs_retriever=docs_retriever,
        code_retriever=code_retriever,
        bm25_docs_retriever=bm25_docs_retriever,
        bm25_code_retriever=bm25_code_retriever,
        k_docs=k_docs,
        k_code=k_code,
        k_bm25_docs=max(0, k_docs),   # simple default: same as dense
        k_bm25_code=max(0, k_code),
    )
    print(f"   ✓ Retriever will ALWAYS include basics + {k_docs} docs + {k_code} code")
    if VECTOR_DB_MODE == "cloud":
        print(f"   ✓ Dense retrieval: Cloud PostgreSQL (pgvector)")
    else:
        print(f"   ✓ Dense retrieval: Local (Chroma)")
    if bm25_code_retriever or bm25_docs_retriever:
        print(f"   ✓ Hybrid retrieval: dense + lexical (BM25) with RRF fusion")
    else:
        print(f"   ⚠️  BM25 disabled: dense retrieval only")
    print(f"   ✓ Cross-encoder reranking enabled")
    print(f"   ✓ Invalid documents will be filtered automatically")
    
    # Azure OpenAI setup
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    
    if not azure_endpoint or not azure_api_key:
        raise ValueError(
            "Azure OpenAI credentials not found!\n"
            "Please set in .env:\n"
            "  AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/\n"
            "  AZURE_OPENAI_API_KEY=your-key-here"
        )

    print(f"\n🔗 Connecting to Azure OpenAI")
    print(f"   Endpoint: {azure_endpoint}")
    print(f"   Deployment: {azure_deployment}")

    with timing_context("Initializing Azure OpenAI client"):
        llm = AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
            api_version=api_version,
            azure_deployment=azure_deployment,
            temperature=1,
        )
    
    # Prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "Conversation context:\n{history}\n\nQuestion: {question}\n\nAvailable Knowledge:\n{context}"),
    ])
    
    # Build chain
    chain_inputs = RunnableParallel(
        question=itemgetter("question"),
        history=itemgetter("history"),
        context=itemgetter("retrieval_query") | enhanced_retriever | format_docs,
    )

    chain = (
        chain_inputs
        | prompt
        | llm
        | StrOutputParser()
    )
    
    init_elapsed = time.time() - init_start
    print("\n✅ RAG chain built successfully!")
    print("   Architecture: Custom Retriever (Basics + Docs + Code)")
    print("   Memory: Enabled (requires 'question', 'history', 'retrieval_query' inputs)")
    print(f"   ⏱️  Total initialization time: {init_elapsed:.2f}s")
    print("=" * 80 + "\n")

    return chain, enhanced_retriever, llm, prompt


def invoke_chain_safe(chain, question: str, history: str = "", retrieval_query: str = None, **kwargs):
    """
    Safely invoke the RAG chain with backward compatibility.
    
    This helper ensures the chain always receives the required 3 inputs,
    even if called with the old single-input pattern.
    
    Args:
        chain: The RAG chain from build_enhanced_chain()
        question: User's question (for LLM prompt)
        history: Conversation history context (empty string if none)
        retrieval_query: Query for vector search (defaults to question)
        **kwargs: Additional inputs (ignored for now)
    
    Returns:
        Chain output (answer string)
    
    Examples:
        # New way (explicit):
        answer = invoke_chain_safe(chain, question="beam?", history="Q1: ...", retrieval_query="beam cross-section")
        
        # Old way (backward compatible):
        answer = invoke_chain_safe(chain, question="beam?")  # history="" and retrieval_query="beam?" auto-set
    """
    if retrieval_query is None:
        retrieval_query = question
    
    inputs = {
        "question": question,
        "history": history,
        "retrieval_query": retrieval_query,
    }
    
    return chain.invoke(inputs)

