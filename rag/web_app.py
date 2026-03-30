"""
Production-ready FastAPI web application for the FemCAD Enhanced RAG assistant.

Features:
- Enhanced RAG with Azure OpenAI (when available)
- Lightweight fallback engine for offline use
- Conversation memory with context-aware query enhancement
- Modern, responsive web UI
- Health monitoring and error handling

Run with:
    uvicorn backend.rag.web_app:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import sys

# Fix SQLite version for ChromaDB on systems with old sqlite3 (e.g. Azure App Service).
# pysqlite3-binary bundles a modern SQLite; monkey-patch before chromadb is imported.
try:
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

# Fix Azure App Service bundled opentelemetry shadowing pip-installed version.
# The bundled version at /agents/python/common/ is outdated and missing ReadableLogRecord.
# Remove these paths entirely and purge any already-loaded opentelemetry modules so
# Python re-imports from the pip-installed (up-to-date) package.
_azure_agent_paths = [p for p in sys.path if '/agents/python/common' in p]
for _p in _azure_agent_paths:
    sys.path.remove(_p)
# Purge cached opentelemetry modules so they reload from the correct location
_otel_mods = [k for k in sys.modules if k.startswith('opentelemetry')]
for _m in _otel_mods:
    del sys.modules[_m]
# Re-add Azure paths at the very end (needed for other Azure agent functionality)
for _p in _azure_agent_paths:
    sys.path.append(_p)

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

import asyncio
import base64
import importlib
import json
import logging
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from .generate import router as generate_router  # noqa: E402

# Import conversation memory with graceful fallback
try:
    from .conversation_memory import memory
except ImportError:
    try:
        from conversation_memory import memory
    except ImportError:
        logging.warning("Could not import conversation_memory. Memory features will be disabled.")
        # Create a dummy memory object if import fails
        from dataclasses import dataclass
        
        @dataclass
        class DummyEnhancedPrompt:
            retrieval_query: str
            context: str
            original_question: str
        
        class DummyMemory:
            def create_session(self): return "dummy-session"
            def ensure_session(self, session_id): return session_id or "dummy-session"
            def enhance_query(self, session_id, question): return question
            def build_context(self, session_id, max_turns=3, answer_preview_chars=180): return ""
            def build_enhanced_prompt(self, session_id, question, max_turns=3, answer_preview_chars=180):
                return DummyEnhancedPrompt(retrieval_query=question, context="", original_question=question)
            def add_turn(self, session_id, question, answer): pass
            def should_update_summary(self, session_id): return False
            def update_summary(self, session_id, new_summary): pass
            def get_stats(self): return {"error": "memory_not_available", "total_sessions": 0, "total_turns": 0, "active_sessions": 0}
        memory = DummyMemory()

# Import storage + auth
# When run as top-level (uvicorn web_app:app from backend/rag), "storage" must be found via path; avoid relative import.
_storage_import_error: Optional[str] = None
_rag_dir = Path(__file__).resolve().parent
_deploy_root = _rag_dir.parent.parent  # backend/rag -> backend -> deploy root
_in_package = "." in __name__  # False when run as "web_app", True when run as "backend.rag.web_app"

# Ensure backend/rag is first on path so "from storage import" finds backend/rag/storage when run as web_app from backend/rag
_rag_dir_str = str(_rag_dir)
if _deploy_root.exists() and str(_deploy_root) not in sys.path:
    sys.path.insert(0, str(_deploy_root))
if _rag_dir_str not in sys.path:
    sys.path.insert(0, _rag_dir_str)

def _try_import_storage():
    """Try importing AzureChatStorage; returns the class or None. Sets _storage_import_error on failure."""
    global _storage_import_error
    errs: List[str] = []
    # 1) "storage" — works when backend/rag is on path (rag dir is now first)
    try:
        from storage import AzureChatStorage
        _storage_import_error = None
        return AzureChatStorage
    except ImportError as e:
        errs.append(f"storage: {e}")
    # 2) "backend.rag.storage" — when deploy root (e.g. femcad-copilot) is on path
    try:
        from backend.rag.storage import AzureChatStorage
        _storage_import_error = None
        return AzureChatStorage
    except ImportError as e:
        errs.append(f"backend.rag.storage: {e}")
    # 3) Relative import only when this module is part of a package
    if _in_package:
        try:
            from .storage import AzureChatStorage
            _storage_import_error = None
            return AzureChatStorage
        except ImportError as e:
            errs.append(f".storage: {e}")
    if errs:
        _storage_import_error = "; ".join(errs)
    return None

AzureChatStorage = _try_import_storage()
if AzureChatStorage is None:
    try:
        from storage import AzureChatStorage
        _storage_import_error = None
    except ImportError as e2:
        _storage_import_error = _storage_import_error or str(e2)
        AzureChatStorage = None  # type: ignore

try:
    from .auth import get_current_user
except ImportError:
    try:
        from auth import get_current_user
    except ImportError:
        get_current_user = None  # type: ignore

# Import fallback engine
try:
    from .web_app_fallback import SimpleFallbackEngine, SimpleDocument
except ImportError:
    try:
        from web_app_fallback import SimpleFallbackEngine, SimpleDocument
    except ImportError:
        logging.error("Could not import fallback engine. Fallback mode will be unavailable.")
        SimpleFallbackEngine = None
        SimpleDocument = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load HTML template from file
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "index.html"
HTML_TEMPLATE = None

def load_html_template() -> str:
    """Load HTML template from file.  Reloads from disk each time so that
    template edits are picked up without restarting the server."""
    try:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"HTML template not found at {TEMPLATE_PATH}")
        return "<html><body><h1>Template not found</h1></body></html>"
    except Exception as e:
        logger.error(f"Error loading HTML template: {e}")
        return "<html><body><h1>Error loading template</h1></body></html>"

# Paths and configuration (standalone repo: repo root is parent of rag/)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASICS_PATH = PROJECT_ROOT / "data" / "femcad_basics_compact.md"
DEFAULT_DOCS_DIR = PROJECT_ROOT / "data" / "documentation"
ENHANCED_MODULE = "rag.chain_builder"

# Load environment variables
# Note: these are re-read on every uvicorn reload.
# Try project root .env first, then backend/rag/.env
_env_path = PROJECT_ROOT / ".env"
_rag_env_path = Path(__file__).parent / ".env"

try:
    load_dotenv(_env_path)
    logger.info(f"Loaded environment from {_env_path}")
except PermissionError as env_exc:
    logger.warning(f"Unable to read {_env_path}: {env_exc}")

# Also load from backend/rag/.env (takes precedence)
try:
    load_dotenv(_rag_env_path, override=True)
    logger.info(f"Loaded environment from {_rag_env_path}")
except PermissionError as env_exc:
    logger.warning(f"Unable to read {_rag_env_path}: {env_exc}")

# Initialize FastAPI app
app = FastAPI(
    title="FemCAD Assistant UI",
    description="Web interface for FemCAD Enhanced RAG assistant",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(generate_router)

# Global state
chain = None
retriever = None
rag_llm = None      # LLM instance for streaming
rag_prompt = None   # Prompt template for streaming
fallback_engine: Optional[SimpleFallbackEngine] = None
startup_error: Optional[str] = None
startup_warning: Optional[str] = None
format_docs_fn = None
chat_store: Optional[AzureChatStorage] = None

SUMMARY_PROMPT = (
    "Summarize this conversation in 6-10 concise bullet points. "
    "Preserve the user's intent, key constraints, important entities, "
    "and any decisions made.\n\n"
)


def _update_summary_background(session_id: str) -> None:
    """Fire-and-forget rolling summary update using rag_llm in a background thread."""
    def _run():
        try:
            context = memory.build_context(session_id, max_turns=memory.max_turns)
            if not context.strip():
                return
            result = rag_llm.invoke(SUMMARY_PROMPT + context)
            text = result.content if hasattr(result, "content") else str(result)
            memory.update_summary(session_id, text)
            logger.debug(f"Summary updated for session {session_id[:8]}...")
        except Exception as exc:
            logger.debug(f"Background summary update failed: {exc}")

    threading.Thread(target=_run, daemon=True).start()


# ===== Pydantic Models =====

class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    question: str = Field(..., min_length=1, max_length=2000, description="User's question")
    session_id: Optional[str] = Field(None, description="Optional session ID for conversation continuity")


class SourceSnippet(BaseModel):
    """Source document snippet."""
    title: str
    source_type: str
    path: Optional[str] = None
    preview: str


class QueryResponse(BaseModel):
    """Response model for query endpoint."""
    answer: str
    context: str
    sources: List[SourceSnippet]
    latency_ms: float
    mode: str
    session_id: str
    conversation_id: str


class ClearSessionRequest(BaseModel):
    """Request model for clearing a session."""
    session_id: str = Field(..., description="Session ID to clear")


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    updated_at: str
    created_at: str
    last_message_preview: str = ""
    metadata: Optional[dict] = None


class MessageItem(BaseModel):
    message_id: str
    role: str
    created_at: str
    content_preview: str
    content: Optional[str] = None
    metadata: Optional[dict] = None


class HealthResponse(BaseModel):
    """Health check response."""
    ready: bool
    error: Optional[str] = None
    warning: Optional[str] = None
    mode: str


# ===== Startup =====

@app.on_event("startup")
async def load_chain() -> None:
    """Build the RAG chain once when the server starts."""
    global chain, retriever, rag_llm, rag_prompt, fallback_engine, startup_error, startup_warning, format_docs_fn, chat_store

    # Reset state
    chain = None
    retriever = None
    rag_llm = None
    rag_prompt = None
    fallback_engine = None
    startup_error = None
    startup_warning = None
    format_docs_fn = _format_docs_local
    chat_store = None

    # Configuration from environment
    k_docs = int(os.getenv("FEMCAD_UI_K_DOCS", "0"))
    k_code = int(os.getenv("FEMCAD_UI_K_CODE", "3"))
    azure_deployment = os.getenv("FEMCAD_UI_DEPLOYMENT", "gpt-5-mini")
    # Default to enhanced RAG unless explicitly disabled.
    enhanced_requested = os.getenv("FEMCAD_UI_ENABLE_ENHANCED", "1").strip().lower() not in {"", "0", "false", "no", "off"}

    logger.info(f"Initializing FemCAD RAG (enhanced={enhanced_requested}, k_docs={k_docs}, k_code={k_code})")

    # Initialize Azure chat storage (optional but preferred)
    if AzureChatStorage:
        try:
            chat_store = AzureChatStorage()
            chat_store.ensure_resources()
            logger.info("✅ Azure chat storage ready.")
        except Exception as exc:
            warn_msg = f"Chat storage unavailable: {exc}"
            startup_warning = warn_msg if not startup_warning else f"{startup_warning} | {warn_msg}"
            logger.warning(f"⚠️  {warn_msg}")
    else:
        detail = f" ({_storage_import_error})" if _storage_import_error else ""
        warn_msg = f"AzureChatStorage not available (import failed){detail}. Persistence disabled."
        startup_warning = warn_msg if not startup_warning else f"{startup_warning} | {warn_msg}"
        logger.warning(f"⚠️  {warn_msg}")

    if get_current_user is None:
        warn_msg = "Auth dependency missing; endpoints requiring auth will fail."
        startup_warning = warn_msg if not startup_warning else f"{startup_warning} | {warn_msg}"
        logger.warning(f"⚠️  {warn_msg}")

    # Try to load enhanced RAG chain
    if enhanced_requested:
        try:
            # Try relative import first (when running from backend/rag/)
            try:
                from .chain_builder import build_enhanced_chain
                from .formatters import format_docs as module_format_docs
            except ImportError:
                # Fallback to absolute import (when running from project root)
                import sys
                if str(PROJECT_ROOT) not in sys.path:
                    sys.path.insert(0, str(PROJECT_ROOT))
                enhanced_module = importlib.import_module(ENHANCED_MODULE)
                build_enhanced_chain = getattr(enhanced_module, "build_enhanced_chain")
                module_format_docs = getattr(enhanced_module, "format_docs", None)
            
            if callable(module_format_docs):
                format_docs_fn = module_format_docs

            chain, retriever, rag_llm, rag_prompt = build_enhanced_chain(
                k_docs=k_docs,
                k_code=k_code,
                azure_deployment=azure_deployment,
            )
            logger.info("✅ FemCAD enhanced RAG ready.")
            return
        except Exception as exc:
            startup_warning = f"Enhanced RAG unavailable ({exc}). Falling back to local search."
            logger.warning(f"⚠️  {startup_warning}")
            import traceback
            logger.debug(traceback.format_exc())
    else:
        startup_warning = "Enhanced RAG disabled (local fallback mode)."
        logger.info("ℹ️  FEMCAD_UI_ENABLE_ENHANCED not set; using fallback engine.")

    # Attempt lightweight fallback so the UI remains usable without heavy deps
    if SimpleFallbackEngine is None:
        startup_error = "Fallback engine not available. Enhanced RAG failed and fallback is unavailable."
        logger.error(f"❌ {startup_error}")
        return

    try:
        fallback_engine = SimpleFallbackEngine(
            project_root=PROJECT_ROOT,
            basics_path=DEFAULT_BASICS_PATH,
            docs_dir=DEFAULT_DOCS_DIR,
            k_docs=k_docs,
        )
        logger.info("✅ Local fallback engine ready.")
    except Exception as fallback_exc:
        startup_error = (
            f"Failed to initialize both enhanced chain and fallback.\n"
            f"Primary issue: {startup_warning}\n"
            f"Fallback issue: {fallback_exc}"
        )
        logger.error(f"❌ {startup_error}")


# ===== Routes =====

@app.get("/health")
def health():
    """App Service / Azure load balancer health check. Returns {"ok": true}."""
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
async def ui() -> HTMLResponse:
    """Serve the web UI."""
    return HTMLResponse(load_html_template())


async def _get_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
) -> Dict[str, str]:
    """Get current user, or return a default user if auth is disabled for local dev."""
    # Check if auth is disabled for local development
    disable_auth = os.getenv("DISABLE_AUTH", "false").lower() in {"true", "1", "yes"}
    
    if disable_auth:
        # Return a default user for local development
        return {"sub": "local-dev-user", "email": "local@dev.local"}
    
    # If auth module not available, allow local dev
    if get_current_user is None:
        return {"sub": "local-dev-user", "email": "local@dev.local"}
    
    # Otherwise, require authentication
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Use the actual auth function
    return await get_current_user(credentials)

@app.post("/api/query", response_model=QueryResponse)
async def query_femcad(
    request: QueryRequest,
    user: Dict[str, str] = Depends(_get_user_optional),
) -> QueryResponse:
    """
    Run a FemCAD RAG query with conversation memory.
    
    Args:
        request: Query request with question and optional session_id
        
    Returns:
        QueryResponse with answer, context, sources, and metadata
        
    Raises:
        HTTPException: If backend is not ready or request is invalid
    """
    if startup_error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=startup_error
        )
    
    backend_ready = chain and retriever
    fallback_ready = fallback_engine is not None
    
    if not backend_ready and not fallback_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FemCAD assistant not ready yet. Try again shortly."
        )
    
    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty."
        )

    try:
        user_id = user.get("sub") if user else None
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User id missing in token",
            )

        # Use provided session_id as conversation_id; create if missing
        requested_id = request.session_id or str(uuid.uuid4())
        
        # Check if session exists in memory
        session_exists = requested_id and requested_id in memory._timestamps
        
        # Ensure session (creates if needed)
        session_id = memory.ensure_session(requested_id)
        conversation_id = session_id  # Keep storage + memory aligned
        
        # Load history from persistent storage if:
        # 1. Session didn't exist in memory (new or expired)
        # 2. Session has no turns yet
        # 3. Storage is available
        if chat_store and (not session_exists or len(memory.get_history(session_id)) == 0):
            try:
                # Try to load history from storage (non-blocking, best-effort)
                memory.load_history_from_storage(
                    session_id=session_id,
                    storage=chat_store,
                    user_id=user_id,
                    max_turns=memory.max_turns
                )
            except Exception as load_exc:
                logger.debug(f"Could not load history from storage for session {session_id[:8]}...: {load_exc}")
        
        # Build enhanced prompt (combines query enhancement + context)
        enhanced_prompt = memory.build_enhanced_prompt(session_id, question)
        
        # Log enhancement (so you can see it working)
        if enhanced_prompt.retrieval_query != question:
            logger.info(f"📝 Enhanced: '{question}' → '{enhanced_prompt.retrieval_query}'")
        
        start = time.perf_counter()
        
        if backend_ready:
            # Use safe invocation helper (imported from rag module if available)
            try:
                from .rag import invoke_chain_safe
            except ImportError:
                try:
                    from rag import invoke_chain_safe
                except ImportError:
                    # Fallback to direct invocation
                    def invoke_chain_safe(chain, question, history="", retrieval_query=None, **kwargs):
                        if retrieval_query is None:
                            retrieval_query = question
                        return chain.invoke({
                            "question": question,
                            "history": history,
                            "retrieval_query": retrieval_query,
                        })
            
            answer = invoke_chain_safe(
                chain,
                question=enhanced_prompt.retrieval_query,
                history=enhanced_prompt.context,
                retrieval_query=enhanced_prompt.retrieval_query,
            )
            # NOTE: This retrieves docs again (chain already retrieved internally).
            # TODO: Optimize by capturing docs from chain's intermediate steps to avoid double retrieval.
            docs = retriever.invoke(enhanced_prompt.retrieval_query)
            mode = "enhanced"
        else:
            if fallback_engine is None:
                raise RuntimeError("Fallback engine not available")
            answer, docs = fallback_engine.run(enhanced_prompt.retrieval_query)
            mode = "fallback"
        
        latency_ms = (time.perf_counter() - start) * 1000
        
        # Store conversation turn (in-memory)
        memory.add_turn(session_id, question, answer)

        # Persist conversation to Azure Storage (best-effort)
        if chat_store:
            try:
                if not chat_store.get_conversation(user_id, conversation_id):
                    chat_store.create_conversation(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        title="Conversation",
                    )
                chat_store.append_message(
                    conversation_id=conversation_id,
                    role="user",
                    content=question,
                    user_id=user_id,
                )
                chat_store.append_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer,
                    user_id=user_id,
                )
                chat_store.upsert_conversation_preview(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    last_message_preview=answer[:512],
                )
            except Exception as storage_exc:
                logger.warning(f"Chat storage write failed: {storage_exc}")
        
        # Update rolling summary in background (non-blocking, best-effort)
        if rag_llm and memory.should_update_summary(session_id):
            _update_summary_background(session_id)
        
        context = format_docs_fn(docs)
        sources = [
            SourceSnippet(
                title=doc.metadata.get("source", "unknown"),
                source_type=doc.metadata.get("type", "retrieved"),
                path=doc.metadata.get("path"),
                preview=doc.page_content,
            )
            for doc in docs
        ]

        return QueryResponse(
            answer=answer,
            context=context,
            sources=sources,
            latency_ms=latency_ms,
            mode=mode,
            session_id=session_id,
            conversation_id=conversation_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Error processing query: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(exc)}"
        ) from exc


@app.post("/api/query/stream")
async def query_femcad_stream(
    request: QueryRequest,
    user: Dict[str, str] = Depends(_get_user_optional),
):
    """
    Stream a FemCAD RAG query response via Server-Sent Events.

    Event types:
      - sources: {context, sources, mode, session_id, conversation_id}
      - token: {token}
      - done: {latency_ms}
      - error: {error}
    """
    # --- Pre-flight validation (same as non-streaming endpoint) ---
    if startup_error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=startup_error)

    backend_ready = chain and retriever and rag_llm and rag_prompt
    fallback_ready = fallback_engine is not None

    if not backend_ready and not fallback_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FemCAD assistant not ready yet. Try again shortly.",
        )

    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question cannot be empty.")

    user_id = user.get("sub") if user else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User id missing in token")

    # Session / memory setup (synchronous, fast)
    requested_id = request.session_id or str(uuid.uuid4())
    session_exists = requested_id and requested_id in memory._timestamps
    session_id = memory.ensure_session(requested_id)
    conversation_id = session_id

    if chat_store and (not session_exists or len(memory.get_history(session_id)) == 0):
        try:
            memory.load_history_from_storage(
                session_id=session_id, storage=chat_store, user_id=user_id, max_turns=memory.max_turns,
            )
        except Exception:
            pass

    enhanced_prompt = memory.build_enhanced_prompt(session_id, question)

    async def _event(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def event_generator():
        start = time.perf_counter()
        full_answer_parts: list[str] = []

        try:
            if backend_ready:
                # 1. Retrieve documents (non-streaming)
                docs = retriever.invoke(enhanced_prompt.retrieval_query)
                context = format_docs_fn(docs)
                sources = [
                    {
                        "title": doc.metadata.get("source", "unknown"),
                        "source_type": doc.metadata.get("type", "retrieved"),
                        "path": doc.metadata.get("path"),
                        "preview": doc.page_content,
                    }
                    for doc in docs
                ]
                mode = "enhanced"

                # 2. Send sources + context up front
                yield await _event("sources", {
                    "context": context,
                    "sources": sources,
                    "mode": mode,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                })

                # 3. Stream LLM tokens
                messages = rag_prompt.format_messages(
                    question=enhanced_prompt.retrieval_query,
                    history=enhanced_prompt.context,
                    context=context,
                )
                async for chunk in rag_llm.astream(messages):
                    token = chunk.content if hasattr(chunk, "content") else str(chunk)
                    if token:
                        full_answer_parts.append(token)
                        yield await _event("token", {"token": token})
            else:
                # Fallback: non-streaming, send as single chunk
                answer, docs = fallback_engine.run(enhanced_prompt.retrieval_query)
                context = format_docs_fn(docs)
                sources = [
                    {
                        "title": doc.metadata.get("source", "unknown"),
                        "source_type": doc.metadata.get("type", "retrieved"),
                        "path": doc.metadata.get("path"),
                        "preview": doc.page_content,
                    }
                    for doc in docs
                ]
                mode = "fallback"
                yield await _event("sources", {
                    "context": context,
                    "sources": sources,
                    "mode": mode,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                })
                full_answer_parts.append(answer)
                yield await _event("token", {"token": answer})

            latency_ms = (time.perf_counter() - start) * 1000
            full_answer = "".join(full_answer_parts)

            # 4. Send done event
            yield await _event("done", {"latency_ms": round(latency_ms, 1)})

            # 5. Persist (best-effort, non-blocking)
            memory.add_turn(session_id, question, full_answer)
            if rag_llm and memory.should_update_summary(session_id):
                _update_summary_background(session_id)

            if chat_store:
                try:
                    if not chat_store.get_conversation(user_id, conversation_id):
                        chat_store.create_conversation(
                            user_id=user_id, conversation_id=conversation_id, title="Conversation",
                        )
                    chat_store.append_message(conversation_id=conversation_id, role="user", content=question, user_id=user_id)
                    chat_store.append_message(conversation_id=conversation_id, role="assistant", content=full_answer, user_id=user_id)
                    chat_store.upsert_conversation_preview(
                        user_id=user_id, conversation_id=conversation_id, last_message_preview=full_answer[:512],
                    )
                except Exception as storage_exc:
                    logger.warning(f"Chat storage write failed: {storage_exc}")

        except Exception as exc:
            logger.exception(f"Streaming error: {exc}")
            yield await _event("error", {"error": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/auth/login")
async def oidc_login(
    request: Request,
    return_to: Optional[str] = Query(None, description="Frontend URL to return to after auth"),
):
    """
    Initiate OIDC login flow by redirecting to the OIDC provider.
    """
    import secrets
    
    # Get OIDC configuration
    oidc_authority = (
        os.getenv("OIDC_AUTHORITY") 
        or os.getenv("AUTH_OIDC_AUTHORITY") 
        or "https://idd.histruct.com"
    ).rstrip("/")
    
    client_id = (
        os.getenv("OIDC_CLIENT_ID")
        or os.getenv("AUTH_OIDC_CLIENT_ID")
        or "histruct-golem-localhost"
    )
    
    # Redirect URI sent to OIDC provider MUST be one registered in the IdP client.
    # Keep it on backend origin and use callback page to relay token to frontend.
    backend_origin = str(request.base_url).rstrip("/")
    redirect_path = os.getenv("AUTH_OIDC_REDIRECT_PATH", "/callback")
    if redirect_path and not redirect_path.startswith("/"):
        redirect_path = f"/{redirect_path}"
    redirect_uri = f"{backend_origin}{redirect_path}" if redirect_path else backend_origin

    frontend_return_url = (
        return_to
        or request.query_params.get("redirect_uri")
        or request.query_params.get("next")
        or request.query_params.get("return_url")
        or os.getenv("AUTH_OIDC_CLIENT_URL")
        or "http://localhost:5174/"
    )
    
    # Log the redirect URI being used for debugging
    logger.info(
        "OIDC Login: Using redirect_uri=%s, client_id=%s, authority=%s",
        redirect_uri,
        client_id,
        oidc_authority,
    )
    
    # Generate state and nonce for security.
    # state packs CSRF token + frontend return URL so callback can relay token to UI.
    state_payload = {
        "csrf": secrets.token_urlsafe(16),
        "return_to": frontend_return_url,
    }
    state_json = json.dumps(state_payload, separators=(",", ":")).encode("utf-8")
    state = base64.urlsafe_b64encode(state_json).decode("ascii").rstrip("=")
    nonce = secrets.token_urlsafe(32)
    
    # Store state in session (for production, use proper session storage)
    # For now, we'll include it in the callback URL
    
    # Get response_mode - form_post is most reliable (server receives token directly,
    # avoids CSP issues with inline JS on callback page that plague fragment mode).
    response_mode = os.getenv("AUTH_OIDC_RESPONSE_MODE", "form_post")
    
    # Build authorization URL
    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "id_token",
        "scope": "openid profile email",
        "response_mode": response_mode,
        "nonce": nonce,
        "state": state,
    }
    
    auth_url = f"{oidc_authority}/connect/authorize?{urlencode(auth_params)}"
    
    return RedirectResponse(url=auth_url)


@app.get("/auth/callback")
async def oidc_callback(
    request: Request,
    id_token: Optional[str] = None,
    error: Optional[str] = None,
    state: Optional[str] = None,
):
    """
    OIDC callback endpoint for token retrieval.
    
    This endpoint receives the redirect from the OIDC provider after authentication.
    Supports both query mode (id_token as query param) and fragment mode (token in URL fragment).
    It stores the token in localStorage via JavaScript and redirects back to the app.
    """
    from fastapi.responses import HTMLResponse
    
    if error:
        # Get backend redirect URI that was attempted for better error messages
        backend_origin = str(request.base_url).rstrip("/")
        redirect_path = os.getenv("AUTH_OIDC_REDIRECT_PATH", "/callback")
        if redirect_path and not redirect_path.startswith("/"):
            redirect_path = f"/{redirect_path}"
        attempted_redirect_uri = f"{backend_origin}{redirect_path}" if redirect_path else backend_origin
        
        error_details = ""
        if error == "unauthorized_client" or "redirect_uri" in error.lower():
            error_details = f"""
            <p><strong>Redirect URI Issue:</strong></p>
            <p>The redirect URI <code>{attempted_redirect_uri}</code> is not registered with HiStruct's OIDC provider.</p>
            <p><strong>To fix this:</strong></p>
            <ol>
                <li>Try setting <code>AUTH_OIDC_REDIRECT_PATH</code> to a different path (e.g., <code>/callback</code> or empty string)</li>
                <li>Or contact your OIDC administrator to register this redirect URI</li>
                <li>Common redirect URI patterns: <code>{client_url}/callback</code>, <code>{client_url}/auth/callback</code>, or <code>{client_url}</code></li>
            </ol>
            """
        
        html = f"""
        <html>
        <head>
            <title>OIDC Error</title>
            <style>
                body {{ font-family: system-ui, sans-serif; padding: 40px; max-width: 700px; margin: 0 auto; }}
                .error {{ background: #fee; border: 2px solid #fcc; padding: 20px; border-radius: 8px; }}
                h1 {{ color: #c33; }}
                code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-family: monospace; }}
                ol {{ margin: 10px 0; padding-left: 20px; }}
                li {{ margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h1>Authentication Error</h1>
                <p><strong>Error:</strong> {error}</p>
                {error_details}
                <p><a href="/">Return to backend</a> | <a href="/auth/login">Try again</a></p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html, status_code=400)
    
    if not id_token:
        # No token in query params — might be fragment mode (token in URL hash).
        # Redirect to the main page preserving the hash so index.html's
        # extractTokenFromHash() can save it.  The <script> handles this;
        # if JS is blocked (CSP), the <noscript>/<meta> fallback still
        # sends the user home with a manual-login prompt.
        html = """
        <html>
        <head>
            <title>Authenticating...</title>
            <noscript><meta http-equiv="refresh" content="0;url=/"></noscript>
        </head>
        <body>
            <p>Redirecting&hellip;</p>
            <div id="error" style="display:none;"></div>
            <script>
                // Extract token from URL fragment (fragment mode) or query params (query mode)
                function showError(msg) {
                    var el = document.getElementById('error');
                    if (el) { el.style.display = 'block'; el.innerHTML = msg; }
                }
                function decodeStateReturnTo(stateValue) {
                    if (!stateValue) return null;
                    try {
                        var padded = stateValue + '='.repeat((4 - stateValue.length % 4) % 4);
                        var jsonText = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
                        var parsed = JSON.parse(jsonText);
                        return parsed && typeof parsed.return_to === 'string' ? parsed.return_to : null;
                    } catch (_e) {
                        return null;
                    }
                }
                function getSafeReturnUrl(candidate) {
                    var fallback = 'http://localhost:5174/';
                    if (!candidate) return fallback;
                    try {
                        var url = new URL(candidate, fallback);
                        if (url.protocol !== 'http:' && url.protocol !== 'https:') return fallback;
                        return url.toString();
                    } catch (_e) {
                        return fallback;
                    }
                }
                function redirectToApp(targetUrl, token) {
                    var url = getSafeReturnUrl(targetUrl);
                    if (token) {
                        window.location.replace(url + '#id_token=' + encodeURIComponent(token));
                        return;
                    }
                    window.location.replace(url);
                }
                function getTokenFromUrl() {
                    try {
                        const hash = window.location.hash.substring(1);
                        const query = window.location.search.substring(1);
                        var targetFromState = null;
                        
                        // Try fragment first (fragment mode)
                        if (hash) {
                            let token = null, error = null;
                            let state = null;
                            try {
                                const params = new URLSearchParams(hash);
                                token = params.get('id_token');
                                error = params.get('error');
                                state = params.get('state');
                            } catch (parseErr) {
                                token = null; error = null; state = null;
                            }
                            if (!token && hash) {
                                var m = hash.match(/id_token=([^&]+)/);
                                if (m) token = m[1]; // keep token as-is (base64url)
                                var e = hash.match(/error=([^&]+)/);
                                if (e) error = decodeURIComponent(e[1].replace(/\\+/g, ' '));
                                var s = hash.match(/state=([^&]+)/);
                                if (s) state = decodeURIComponent(s[1].replace(/\\+/g, ' '));
                            }
                            targetFromState = decodeStateReturnTo(state);
                            
                            if (error) {
                                showError('<strong>Error:</strong> ' + error + '<br><a href="/">Return to app</a>');
                                return;
                            }
                            
                            if (token) {
                                try {
                                    localStorage.setItem('histruct_id_token', token);
                                    localStorage.setItem('histruct_token_timestamp', Date.now().toString());
                                } catch (e) {
                                    showError('Could not save token: ' + e.message + '<br><a href="/">Continue to app</a>');
                                    return;
                                }
                                redirectToApp(targetFromState, token);
                                return;
                            }
                        }
                        
                        // Try query params (query mode)
                        if (query) {
                            const params = new URLSearchParams(query);
                            const token = params.get('id_token');
                            const error = params.get('error');
                            const state = params.get('state');
                            targetFromState = decodeStateReturnTo(state);
                            
                            if (error) {
                                showError('<strong>Error:</strong> ' + error + '<br><a href="/">Return to app</a>');
                                return;
                            }
                            
                            if (token) {
                                try {
                                    localStorage.setItem('histruct_id_token', token);
                                    localStorage.setItem('histruct_token_timestamp', Date.now().toString());
                                } catch (e) {
                                    showError('Could not save token: ' + e.message + '<br><a href="/">Continue to app</a>');
                                    return;
                                }
                                redirectToApp(targetFromState, token);
                                return;
                            }
                        }
                        
                        // No token found
                        showError("<strong>No token received</strong><br>Check the URL in your browser's address bar.<br><a href=\"/\">Return to app</a>");
                    } catch (e) {
                        showError('Unexpected error: ' + e.message + '<br><a href="/">Continue to app</a>');
                    }
                }
                
                getTokenFromUrl();
                // If redirect did not happen within 3s, show a manual link so user is never stuck
                setTimeout(function() {
                    if (window.location.pathname.indexOf('callback') !== -1) {
                        var el = document.getElementById('error');
                        if (el && el.style.display !== 'block') {
                            el.style.display = 'block';
                            el.innerHTML = 'Redirect did not start. <a href="/">Continue to app</a> or <a href="/auth/login">try again</a>.';
                        }
                    }
                }, 3000);
            </script>
            <noscript><p>If not redirected, <a href="/">click here</a>.</p></noscript>
        </body>
        </html>
        """
        return HTMLResponse(content=html)
    
    # Query mode token branch: store token and relay to frontend app.
    html = f"""
    <html>
    <head>
        <title>Authenticating...</title>
        <style>
            body {{
                font-family: system-ui, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(120deg, #e6e9ff 0%, #f8f9ff 100%);
            }}
            .container {{
                text-align: center;
                padding: 40px;
                background: white;
                border-radius: 16px;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
            }}
            .spinner {{
                border: 4px solid #f3f3f3;
                border-top: 4px solid #6c63ff;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 20px auto;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            h1 {{
                color: #6c63ff;
                margin: 0 0 10px;
            }}
            p {{
                color: #666;
                margin: 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>✅ Authentication Successful!</h1>
            <div class="spinner"></div>
            <p>Redirecting to app...</p>
        </div>
        <script>
            // Store token in localStorage
            localStorage.setItem('histruct_id_token', '{id_token}');
            localStorage.setItem('histruct_token_timestamp', Date.now().toString());
            var target = 'http://localhost:5174/';
            try {{
                if ('{state or ""}') {{
                    var padded = '{state or ""}' + '='.repeat((4 - ('{state or ""}'.length % 4)) % 4);
                    var jsonText = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
                    var parsed = JSON.parse(jsonText);
                    if (parsed && typeof parsed.return_to === 'string') {{
                        target = parsed.return_to;
                    }}
                }}
            }} catch (_e) {{}}
            
            // Redirect to main app after a short delay
            setTimeout(function() {{
                window.location.href = target + '#id_token=' + encodeURIComponent('{id_token}');
            }}, 1000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/callback")
async def oidc_callback_alt(
    request: Request,
    id_token: Optional[str] = None,
    error: Optional[str] = None,
    state: Optional[str] = None,
):
    """
    Alternative OIDC callback endpoint at /callback (common redirect URI pattern).
    This is a convenience endpoint that delegates to the main callback handler.
    """
    return await oidc_callback(request=request, id_token=id_token, error=error, state=state)


@app.post("/auth/callback")
async def oidc_callback_post(
    request: Request,
    id_token: Optional[str] = Form(None),
    error: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
):
    """OIDC callback for response_mode=form_post (token arrives as POST form field)."""
    return await oidc_callback(request=request, id_token=id_token, error=error, state=state)


@app.post("/callback")
async def oidc_callback_alt_post(
    request: Request,
    id_token: Optional[str] = Form(None),
    error: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
):
    """Alternative OIDC callback POST endpoint at /callback for form_post mode."""
    return await oidc_callback(request=request, id_token=id_token, error=error, state=state)


@app.get("/auth/logout")
async def oidc_logout():
    """
    Logout endpoint that clears the stored token.
    """
    from fastapi.responses import HTMLResponse
    
    html = """
    <html>
    <head>
        <title>Logging out...</title>
        <style>
            body {
                font-family: system-ui, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(120deg, #e6e9ff 0%, #f8f9ff 100%);
            }
            .container {
                text-align: center;
                padding: 40px;
                background: white;
                border-radius: 16px;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Logging out...</h1>
            <p>Redirecting...</p>
        </div>
        <script>
            // Clear token from localStorage
            localStorage.removeItem('histruct_id_token');
            localStorage.removeItem('histruct_token_timestamp');
            
            // Redirect to main app
            setTimeout(function() {
                window.location.href = '/';
            }, 500);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns:
        HealthResponse with status information
    """
    mode = "enhanced" if chain else ("fallback" if fallback_engine else "unavailable")
    ready = startup_error is None and mode != "unavailable"
    return HealthResponse(
        ready=ready,
        error=startup_error,
        warning=startup_warning,
        mode=mode,
    )


@app.get("/api/memory/stats")
async def memory_stats() -> dict:
    """Get conversation memory statistics."""
    return memory.get_stats()


@app.post("/api/memory/clear")
async def clear_session(request: ClearSessionRequest) -> dict:
    """
    Clear a specific session's conversation history.
    
    Args:
        request: ClearSessionRequest with session_id
        
    Returns:
        Status dictionary
    """
    session_id = request.session_id
    if hasattr(memory, 'conversations') and session_id in memory.conversations:
        del memory.conversations[session_id]
        if hasattr(memory, 'session_timestamps') and session_id in memory.session_timestamps:
            del memory.session_timestamps[session_id]
        logger.info(f"Cleared session: {session_id}")
        return {"status": "cleared", "session_id": session_id}
    return {"status": "not_found", "session_id": session_id}


# ===== Conversation persistence (Azure Storage) =====


def _require_chat_store() -> AzureChatStorage:
    if chat_store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat storage not configured",
        )
    return chat_store


@app.get("/api/conversations", response_model=List[ConversationSummary])
async def list_conversations(user: Dict[str, str] = Depends(_get_user_optional)):
    store = _require_chat_store()
    user_id = user.get("sub") if user else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user id")
    convs = store.list_conversations(user_id=user_id)
    summaries = [
        ConversationSummary(
            conversation_id=c.conversation_id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            last_message_preview=c.last_message_preview,
            metadata=c.metadata,
        )
        for c in convs
    ]
    return summaries


@app.get("/api/conversations/{conversation_id}/messages", response_model=List[MessageItem])
async def list_messages(
    conversation_id: str,
    full: bool = Query(False, description="If true, include full message bodies"),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Max messages to return"),
    user: Dict[str, str] = Depends(_get_user_optional),
):
    store = _require_chat_store()
    user_id = user.get("sub") if user else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user id")
    conv = store.get_conversation(user_id=user_id, conversation_id=conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    records = store.list_messages(conversation_id=conversation_id, limit=limit)
    items: List[MessageItem] = []
    for rec in records:
        content = store.get_message_body(rec) if full else None
        items.append(
            MessageItem(
                message_id=rec.message_id,
                role=rec.role,
                created_at=rec.created_at,
                content_preview=rec.content_preview,
                content=content,
                metadata=rec.metadata,
            )
        )
    return items


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: Dict[str, str] = Depends(_get_user_optional),
) -> dict:
    store = _require_chat_store()
    user_id = user.get("sub") if user else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user id")
    conv = store.get_conversation(user_id=user_id, conversation_id=conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    store.delete_conversation(user_id=user_id, conversation_id=conversation_id)
    return {"status": "deleted", "conversation_id": conversation_id}


# ===== Helper Functions =====

def _format_docs_local(docs: List[SimpleDocument]) -> str:
    """
    Format retrieved documents similar to the enhanced pipeline.
    
    Args:
        docs: List of SimpleDocument objects
        
    Returns:
        Formatted context string
    """
    parts = []
    basics_found = False
    doc_count = 0
    code_count = 0

    for doc in docs:
        meta = doc.metadata or {}
        doc_type = meta.get("type", "unknown")
        src = meta.get("source", "unknown")

        if doc_type == "always_included" and not basics_found:
            parts.append("=" * 80)
            parts.append("📘 FEMCAD FUNDAMENTALS (Always Included)")
            parts.append("=" * 80)
            parts.append(doc.page_content)
            basics_found = True
        elif "code" in src.lower() or meta.get("path", "").endswith((".fcs", ".fcc")):
            code_count += 1
            if code_count == 1:
                parts.append("\n" + "=" * 80)
                parts.append("💻 CODE EXAMPLES")
                parts.append("=" * 80)

            path = meta.get("path", "")
            header = f"\n--- Code Example {code_count}: {src}"
            if path:
                header += f" ({path})"
            parts.append(header + " ---")
            parts.append(doc.page_content)
        else:
            doc_count += 1
            if doc_count == 1:
                parts.append("\n" + "=" * 80)
                parts.append("📚 RELEVANT DOCUMENTATION")
                parts.append("=" * 80)

            path = meta.get("path", "")
            header = f"\n--- Doc {doc_count}: {src}"
            if path:
                header += f" ({path})"
            parts.append(header + " ---")
            parts.append(doc.page_content)

    return "\n".join(parts)


# Set default format function
format_docs_fn = _format_docs_local


# ===== Main Entry Point =====

if __name__ == "__main__":
    import uvicorn

    # Azure App Service and most PaaS set PORT; default 8000 for local dev
    port = int(os.environ.get("PORT", "8000"))
    logger.info("Starting FemCAD Assistant Web UI...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
