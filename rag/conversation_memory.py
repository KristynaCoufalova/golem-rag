"""
Enhanced Conversation Memory for Golem Web App

In-memory conversation storage with rolling summaries and context-aware query enhancement.

Features:
- Keeps last N raw turns (e.g., 12)
- Maintains rolling summary (updated every few turns)
- Thread-safe operations
- Automatic TTL cleanup
- Context-aware query enhancement
- Token-based context limits (more accurate than character-based)
- Lazy loading from persistent storage (Azure)
- Smart context prioritization

Easily upgradable to Redis for persistence.

Usage in web_app.py or rag.py:

    from conversation_memory import memory

    # Get or create session (with optional storage for persistence)
    session_id = request.session_id or memory.ensure_session(request.session_id)
    
    # Optionally load history from persistent storage if session is new in memory
    if storage:
        memory.load_history_from_storage(session_id, storage, user_id)
    
    # Build enhanced prompt (combines query enhancement + context)
    enhanced_prompt = memory.build_enhanced_prompt(session_id, question)
    
    # Use in RAG chain:
    # - enhanced_prompt.retrieval_query for retrieval/search
    # - enhanced_prompt.context for LLM history context
    answer = chain.invoke({
        "question": enhanced_prompt.retrieval_query,
        "history": enhanced_prompt.context,
        "retrieval_query": enhanced_prompt.retrieval_query,
    })
    
    # Store the turn
    memory.add_turn(session_id, question, answer)
    
    # Update summary occasionally (optional but recommended)
    if memory.should_update_summary(session_id):
        summarizer_input = memory.build_context(session_id, max_turns=memory.max_turns)
        new_summary = summarizer_llm.invoke(
            "Summarize the conversation so far in 8-12 bullet points, "
            "preserving user intent, constraints, and important entities.\n\n"
            + summarizer_input
        )
        memory.update_summary(session_id, new_summary)

Note: The build_enhanced_prompt() method is the recommended way to use memory
in RAG pipelines. The individual enhance_query() and build_context() methods
are still available for backward compatibility or advanced use cases.
"""

import uuid
import re
import threading
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict

# Try to import token counting utilities
try:
    from .utils import count_tokens, TIKTOKEN_AVAILABLE
except ImportError:
    try:
        from utils import count_tokens, TIKTOKEN_AVAILABLE
    except ImportError:
        TIKTOKEN_AVAILABLE = False
        def count_tokens(text: str) -> int:
            # Fallback: rough estimate (1 token ≈ 4 characters)
            return len(text) // 4

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """Single turn in a conversation"""
    question: str
    answer: str
    timestamp: str
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EnhancedPrompt:
    """Enhanced prompt with query and context for RAG"""
    retrieval_query: str  # Enhanced query for retrieval/search
    context: str  # Conversation history context for LLM
    original_question: str  # Original user question (for logging)
    
    def to_dict(self) -> dict:
        return asdict(self)


class ConversationMemory:
    """
    Enhanced in-memory conversation storage with rolling summaries.
    
    Features:
    - Session-based conversation tracking
    - Rolling summaries (compressed older context)
    - Last N raw turns (recent context)
    - Thread-safe operations
    - Automatic cleanup of old sessions
    - Context-aware query enhancement for follow-up questions
    - Extract key topics from conversation history
    """
    
    def __init__(self, 
                 max_turns_per_session: int = 12,
                 session_ttl_hours: int = 24,
                 summary_update_every: int = 4,
                 max_answer_preview_chars: int = 220,
                 max_context_chars: int = 2600,
                 max_context_tokens: Optional[int] = None,
                 use_token_limits: bool = True):
        """
        Args:
            max_turns_per_session: Keep last N raw conversation turns
            session_ttl_hours: Hours before session expires
            summary_update_every: Update summary after every N new turns
            max_answer_preview_chars: Max characters for answer previews in context (fallback)
            max_context_chars: Hard cap for LLM history context (fallback if tokens unavailable)
            max_context_tokens: Max tokens for context (default: ~650 tokens, roughly 2600 chars)
            use_token_limits: Use token-based limits if tiktoken available, else character-based
        """
        self._turns: Dict[str, List[ConversationTurn]] = defaultdict(list)
        self._summary: Dict[str, str] = defaultdict(str)
        self._timestamps: Dict[str, datetime] = {}
        self._new_turns_since_summary: Dict[str, int] = defaultdict(int)
        self._loaded_from_storage: Dict[str, bool] = {}  # Track which sessions loaded from storage
        self._lock = threading.RLock()
        
        self.max_turns = max_turns_per_session
        self.ttl = timedelta(hours=session_ttl_hours)
        self.summary_update_every = summary_update_every
        self.max_answer_preview_chars = max_answer_preview_chars
        self.max_context_chars = max_context_chars
        self.use_token_limits = use_token_limits and TIKTOKEN_AVAILABLE
        
        # Token-based limits (more accurate)
        if max_context_tokens is None:
            # Rough conversion: 1 token ≈ 4 chars, so 2600 chars ≈ 650 tokens
            # But we'll be a bit more generous for token-based
            max_context_tokens = 800
        self.max_context_tokens = max_context_tokens
        
        # Backward compatibility aliases
        self.conversations = self._turns
        self.session_timestamps = self._timestamps
        self.session_ttl = self.ttl
    
    def create_session(self) -> str:
        """Create new session ID"""
        with self._lock:
            sid = str(uuid.uuid4())
            self._timestamps[sid] = datetime.now()
            self._turns[sid] = []
            self._summary[sid] = ""
            self._new_turns_since_summary[sid] = 0
            return sid
    
    def ensure_session(self, session_id: Optional[str]) -> str:
        """
        Ensure session exists, creating if needed or refreshing timestamp if exists.
        
        Args:
            session_id: Optional existing session ID
            
        Returns:
            Valid session ID (existing or newly created)
        """
        with self._lock:
            if session_id and session_id in self._timestamps:
                self._timestamps[session_id] = datetime.now()
                return session_id
            return self.create_session()
    
    def load_history_from_storage(self, 
                                   session_id: str, 
                                   storage: Any,
                                   user_id: str,
                                   max_turns: Optional[int] = None) -> bool:
        """
        Load conversation history from persistent storage (e.g., Azure).
        
        This is called when resuming a session that doesn't exist in memory.
        Only loads if not already loaded (idempotent).
        
        Args:
            session_id: Session/conversation ID
            storage: Storage client (e.g., AzureChatStorage) with list_messages() and get_message_body()
            user_id: User ID for storage lookup
            max_turns: Maximum turns to load (default: self.max_turns)
            
        Returns:
            True if history was loaded, False if already loaded or failed
        """
        with self._lock:
            # Skip if already loaded or if session already has turns
            if self._loaded_from_storage.get(session_id, False):
                return False
            if session_id in self._turns and len(self._turns[session_id]) > 0:
                self._loaded_from_storage[session_id] = True
                return False
        
        try:
            # Load messages from storage
            if not hasattr(storage, 'list_messages'):
                logger.warning(f"Storage client missing list_messages method")
                return False
            
            messages = storage.list_messages(conversation_id=session_id, limit=max_turns or self.max_turns)
            
            if not messages:
                with self._lock:
                    self._loaded_from_storage[session_id] = True
                return False
            
            # Group messages into turns (user + assistant pairs)
            turns = []
            current_user_msg = None
            
            for msg_record in messages:
                if msg_record.role == "user":
                    current_user_msg = msg_record
                elif msg_record.role == "assistant" and current_user_msg:
                    # Get full message bodies
                    user_content = storage.get_message_body(current_user_msg) if hasattr(storage, 'get_message_body') else current_user_msg.content_preview
                    assistant_content = storage.get_message_body(msg_record) if hasattr(storage, 'get_message_body') else msg_record.content_preview
                    
                    if user_content and assistant_content:
                        turns.append(ConversationTurn(
                            question=user_content,
                            answer=assistant_content,
                            timestamp=msg_record.created_at or datetime.now().isoformat()
                        ))
                    current_user_msg = None
            
            # Add turns to memory (most recent first, so reverse)
            with self._lock:
                if session_id not in self._turns:
                    self._turns[session_id] = []
                    self._timestamps[session_id] = datetime.now()
                    self._summary[session_id] = ""
                    self._new_turns_since_summary[session_id] = 0
                
                # Prepend older turns (they're already in chronological order)
                self._turns[session_id] = turns + self._turns[session_id]
                
                # Keep only last N turns
                if len(self._turns[session_id]) > self.max_turns:
                    self._turns[session_id] = self._turns[session_id][-self.max_turns:]
                
                self._loaded_from_storage[session_id] = True
                logger.info(f"Loaded {len(turns)} turns from storage for session {session_id[:8]}...")
                return True
                
        except Exception as e:
            logger.warning(f"Failed to load history from storage for session {session_id}: {e}")
            with self._lock:
                self._loaded_from_storage[session_id] = True  # Mark as attempted to avoid retries
            return False
    
    def add_turn(self, 
                 session_id: str, 
                 question: str, 
                 answer: str):
        """
        Add a conversation turn.
        
        Args:
            session_id: Session identifier
            question: User's question
            answer: Assistant's answer
        """
        with self._lock:
            sid = self.ensure_session(session_id)
            
            self._turns[sid].append(
                ConversationTurn(
                    question=question.strip(),
                    answer=answer.strip(),
                    timestamp=datetime.now().isoformat(),
                )
            )
            self._timestamps[sid] = datetime.now()
            self._new_turns_since_summary[sid] += 1
            
            # Keep last N turns
            if len(self._turns[sid]) > self.max_turns:
                self._turns[sid] = self._turns[sid][-self.max_turns:]
            
            self._cleanup()
    
    def get_history(self, 
                    session_id: str, 
                    max_turns: Optional[int] = None) -> List[ConversationTurn]:
        """
        Get conversation history.
        
        Args:
            session_id: Session identifier
            max_turns: Maximum turns to return (default: all)
        
        Returns:
            List of conversation turns
        """
        with self._lock:
            if session_id not in self._turns:
                return []
            
            history = self._turns[session_id]
            if max_turns:
                return history[-max_turns:]
            return history

    def build_enhanced_prompt(self,
                             session_id: str,
                             question: str,
                             max_turns_in_context: int = 6,
                             answer_preview_chars: Optional[int] = None) -> EnhancedPrompt:
        """
        Build enhanced prompt combining query enhancement and context building.
        
        This is the main method for RAG integration - it combines:
        - Query enhancement (for better retrieval)
        - Context building (for LLM prompt) with summary + recent turns
        
        Args:
            session_id: Session identifier
            question: Current user question
            max_turns_in_context: Maximum conversation turns to include in context
            answer_preview_chars: Max characters for answer previews (uses instance default if None)
            
        Returns:
            EnhancedPrompt with retrieval_query, context, and original_question
        """
        sid = self.ensure_session(session_id)
        retrieval_query = self.enhance_query(sid, question)
        
        # Use instance default if not provided
        if answer_preview_chars is None:
            answer_preview_chars = self.max_answer_preview_chars
        
        context = self.build_context(sid, max_turns=max_turns_in_context, 
                                    answer_preview_chars=answer_preview_chars)
        
        return EnhancedPrompt(
            retrieval_query=retrieval_query,
            context=context,
            original_question=question
        )

    def build_context(self,
                      session_id: str,
                      max_turns: int = 6,
                      answer_preview_chars: Optional[int] = None) -> str:
        """
        Build a compact string with summary + recent conversation turns.
        
        Uses token-based limits if available (more accurate), otherwise character-based.
        Smart prioritization: includes summary + recent turns, trimming from oldest if needed.
        
        Format:
        - Conversation summary (if available)
        - Recent turns (last N turns, compacted)
        
        Note: For RAG integration, prefer build_enhanced_prompt() which combines
        this with query enhancement.
        """
        with self._lock:
            if session_id not in self._timestamps:
                return ""
            
            if answer_preview_chars is None:
                answer_preview_chars = self.max_answer_preview_chars
            
            summary = (self._summary.get(session_id) or "").strip()
            turns = self._turns.get(session_id, [])[-max_turns:]
            
            parts: List[str] = []
            
            if summary:
                parts.append("Conversation summary so far:")
                parts.append(summary)
            
            if turns:
                parts.append("Recent turns:")
                for i, t in enumerate(turns, start=1):
                    a = self._compact(t.answer, answer_preview_chars)
                    parts.append(f"User: {t.question}")
                    parts.append(f"Assistant: {a}")
            
            text = "\n".join(parts).strip()
            
            # Apply limits (token-based if available, else character-based)
            if self.use_token_limits:
                tokens = count_tokens(text)
                if tokens > self.max_context_tokens:
                    # Trim from the beginning (oldest content) while preserving structure
                    text = self._trim_to_token_limit(text, self.max_context_tokens, summary, turns)
            else:
                # Character-based fallback
                if len(text) > self.max_context_chars:
                    text = text[-self.max_context_chars:]
                    text = "…(trimmed)\n" + text
            
            return text
    
    def _trim_to_token_limit(self, 
                             text: str, 
                             max_tokens: int,
                             summary: str,
                             turns: List[ConversationTurn]) -> str:
        """
        Trim context to token limit, prioritizing recent content.
        
        Strategy:
        1. Always keep summary if it fits
        2. Keep as many recent turns as possible
        3. Trim from oldest turns if needed
        """
        # Start with summary if available
        parts: List[str] = []
        summary_text = ""
        if summary:
            summary_text = f"Conversation summary so far:\n{summary}"
            summary_tokens = count_tokens(summary_text)
            if summary_tokens <= max_tokens * 0.4:  # Use up to 40% for summary
                parts.append(summary_text)
                remaining_tokens = max_tokens - summary_tokens
            else:
                # Summary too long, truncate it
                summary_text = summary[:len(summary) // 2] + "..."
                parts.append(f"Conversation summary so far:\n{summary_text}")
                remaining_tokens = max_tokens - count_tokens(parts[0])
        else:
            remaining_tokens = max_tokens
        
        # Add turns from most recent, working backwards
        turns_text = []
        for turn in reversed(turns):  # Start with most recent
            turn_text = f"User: {turn.question}\nAssistant: {self._compact(turn.answer, self.max_answer_preview_chars)}"
            turn_tokens = count_tokens(turn_text)
            
            if turn_tokens <= remaining_tokens:
                turns_text.insert(0, turn_text)  # Prepend to maintain order
                remaining_tokens -= turn_tokens
            else:
                break  # Can't fit more turns
        
        if turns_text:
            parts.append("Recent turns:")
            parts.extend(turns_text)
        
        result = "\n".join(parts).strip()
        
        # Final safety check
        if count_tokens(result) > max_tokens:
            # Last resort: truncate from start
            result = "…(trimmed)\n" + self._truncate_by_tokens(result, max_tokens - 20, from_start=True)
        
        return result
    
    def _truncate_by_tokens(self, text: str, max_tokens: int, from_start: bool = False) -> str:
        """Truncate text to fit within token limit."""
        if not self.use_token_limits:
            # Fallback to character-based
            if from_start:
                return text[-self.max_context_chars:]
            return text[:self.max_context_chars]
        
        tokens = count_tokens(text)
        if tokens <= max_tokens:
            return text
        
        # Binary search for the right length
        if from_start:
            # Truncate from start (keep end)
            low, high = 0, len(text)
            while low < high:
                mid = (low + high + 1) // 2
                candidate = text[mid:]
                if count_tokens(candidate) <= max_tokens:
                    high = mid - 1
                else:
                    low = mid
            return text[low:]
        else:
            # Truncate from end (keep start)
            low, high = 0, len(text)
            while low < high:
                mid = (low + high) // 2
                candidate = text[:mid]
                if count_tokens(candidate) <= max_tokens:
                    low = mid + 1
                else:
                    high = mid
            return text[:low]

    def enhance_query(self, session_id: str, question: str) -> str:
        """
        Enhance query with conversation context.
        
        Keep retrieval query mostly unchanged to avoid polluting retrieval.
        Only add minimal topic context for clear follow-ups.
        
        Handles follow-up questions like:
        - "What about X?" → "beam What about X?" (if previous was about beams)
        - "And the cross-section?" → "beam cross-section" (adds context)
        - "How do I do that?" → Uses previous topic
        
        Args:
            session_id: Session identifier
            question: Current question
        
        Returns:
            Enhanced question with context (or original if not a follow-up)
        """
        q = question.strip()
        history = self._turns.get(session_id, [])[-2:]
        
        if not history:
            return q
        
        if not self._is_follow_up(q):
            return q
        
        topic = self._extract_topic(" ".join([h.question for h in history]))
        return f"{topic} {q}".strip() if topic else q
    
    def should_update_summary(self, session_id: str) -> bool:
        """
        Check if summary should be updated for this session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if summary should be updated
        """
        with self._lock:
            return self._new_turns_since_summary.get(session_id, 0) >= self.summary_update_every
    
    def update_summary(self, session_id: str, new_summary: str) -> None:
        """
        Update the rolling summary for a session.
        
        Call this with the result of a summarizer LLM call.
        
        Args:
            session_id: Session identifier
            new_summary: New summary text from summarizer
        """
        with self._lock:
            self._summary[session_id] = new_summary.strip()
            self._new_turns_since_summary[session_id] = 0
    
    @staticmethod
    def _is_follow_up(q: str) -> bool:
        """Check if question is a follow-up (needs context)"""
        ql = q.lower().strip()
        
        # Patterns that indicate follow-up questions
        if re.match(r"^(what about|how about|and |but |also |what if)\b", ql):
            return True
        if re.match(r"^(this|that|it|they|these|those)\b", ql):
            return True
        if ql in {"?", "why", "how", "ok", "okay"}:
            return True
        
        # Short AND vague
        tokens = re.findall(r"[a-zA-Z0-9_\-]+", ql)
        return len(tokens) <= 3 and not any(len(t) >= 5 for t in tokens)
    
    def _is_follow_up_question(self, question: str) -> bool:
        """Backward compatibility alias"""
        return self._is_follow_up(question)
    
    @staticmethod
    def _extract_topic(text: str) -> str:
        """
        Extract key topic from text.
        Prefer FemCAD-ish keywords if present, otherwise first meaningful token.
        """
        # FemCAD-specific keywords that indicate topics
        keywords = [
            "beam", "gblock", "gclass", "mesh", "material", "load",
            "support", "constraint", "cross-section", "analysis", "model",
            "point", "vertex", "curve", "force", "coordinate system",
            "transformation", "FEM", "geometry",
        ]
        
        tl = text.lower()
        for k in keywords:
            if k in tl:
                return k
        
        # Fallback: first "meaningful" token
        toks = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]{3,}", tl)
        stop = {"what", "how", "when", "where", "which", "that", "this", "with", "from", "about"}
        for t in toks:
            if t not in stop:
                return t
        return ""
    
    def _extract_topics(self, history: List[ConversationTurn]) -> str:
        """Backward compatibility alias - extract topics from history"""
        if not history:
            return ""
        recent_text = " ".join([turn.question for turn in history])
        return self._extract_topic(recent_text)
    
    @staticmethod
    def _compact(text: str, limit: int) -> str:
        """
        Compact text by removing code blocks and truncating.
        
        Args:
            text: Text to compact
            limit: Maximum characters
            
        Returns:
            Compacted text
        """
        # Remove code blocks (optional, helps keep it short)
        text = re.sub(r"```.*?```", "[code omitted]", text, flags=re.S)
        text = text.replace("\n", " ").strip()
        return text[:limit].rstrip() + ("..." if len(text) > limit else "")
    
    def _cleanup(self) -> None:
        """Remove expired sessions"""
        now = datetime.now()
        expired = [sid for sid, ts in self._timestamps.items() if now - ts > self.ttl]
        
        for sid in expired:
            self._timestamps.pop(sid, None)
            self._turns.pop(sid, None)
            self._summary.pop(sid, None)
            self._new_turns_since_summary.pop(sid, None)
    
    def _cleanup_old_sessions(self):
        """Backward compatibility alias"""
        self._cleanup()
    
    def get_stats(self) -> dict:
        """Get memory statistics"""
        with self._lock:
            return {
                "total_sessions": len(self._turns),
                "total_turns": sum(len(turns) for turns in self._turns.values()),
                "sessions_with_summaries": len([s for s in self._summary.values() if s]),
                "active_sessions": len([
                    sid for sid, timestamp in self._timestamps.items()
                    if datetime.now() - timestamp < timedelta(hours=1)
                ])
            }


# Global singleton instance
memory = ConversationMemory(
    max_turns_per_session=12,  # Keep last 12 raw turns
    session_ttl_hours=24,  # Sessions expire after 24 hours
    summary_update_every=4,  # Update summary after every 4 new turns
    max_answer_preview_chars=220,  # Max chars for answer previews (fallback)
    max_context_chars=2600,  # Hard cap for LLM history context (fallback)
    max_context_tokens=800,  # Token-based limit (more accurate, ~3200 chars)
    use_token_limits=True,  # Use token counting if available
)


