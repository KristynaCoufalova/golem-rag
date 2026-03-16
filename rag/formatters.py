"""
Document formatting and system prompt for FemCAD RAG system.
"""

import time
from typing import List

from langchain_core.documents import Document

from .utils import count_tokens, format_token_count
from .config import set_last_formatted_context_tokens


# ===== SYSTEM PROMPT (with escaped braces) =====
SYSTEM_PROMPT = """You are an expert FemCAD assistant.

You receive context that ALWAYS includes:
1. **FemCAD Fundamentals**: Complete syntax reference (always first)
2. **Documentation**: Relevant concept explanations (retrieved)
3. **Code Examples**: Working code snippets (retrieved)

YOUR APPROACH:
1. Ground every answer in the Fundamentals - they are authoritative
2. Use Documentation to explain concepts in detail
3. Show Code Examples for practical implementation
4. Maintain strict FemCAD conventions from the fundamentals

CRITICAL RULES:
✓ Trust the fundamentals completely - they define FemCAD syntax
✓ Follow conventions exactly:
  - Identifiers: {{v1}}, {{c1}}, {{gb}} (braces required)
  - Naming: camelCase (variables), PascalCase (types)
  - Case-sensitive: Fcs. not FCS.
  - Arrays: 0-indexed
  - Units: Unit.kN, Unit.m, Unit.deg
✓ NEVER invent syntax not shown in fundamentals or examples
✓ If fundamentals + retrieved context don't cover it, say so
✓ Preserve exact formatting from code examples 
✓ ALWAYS check all source files mentioned in the code snippet as some objects may be defined in different source file 
✓ GOOD solutions OFTEN span multiple well-named fcs files / gclasses

RESPONSE STYLE:
- Direct answers grounded in fundamentals
- Show code examples when relevant
- Concise explanations unless detail requested
- Reference source files when helpful
- ALWAYS wrap code in fenced markdown blocks with a language tag
  (use ```fcs for FemCAD, otherwise ```text)"""


# ===== FORMATTING =====
def format_docs(docs: List[Document]) -> str:
    """Format retrieved documents for context"""
    start = time.time()
    
    parts = []
    basics_found = False
    doc_count = 0
    code_count = 0
    
    for d in docs:
        meta = d.metadata or {}
        doc_type = meta.get("type", "unknown")
        src = meta.get("source", "unknown")
        
        if doc_type == "always_included" and not basics_found:
            parts.append("=" * 80)
            parts.append("📘 FEMCAD FUNDAMENTALS (Always Included)")
            parts.append("=" * 80)
            parts.append(d.page_content)
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
            parts.append(d.page_content)
            
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
            parts.append(d.page_content)
    
    result = "\n".join(parts)
    elapsed = time.time() - start
    formatted_tokens = count_tokens(result)
    set_last_formatted_context_tokens(formatted_tokens)
    print(f"   ⏱️  Formatting documents: {elapsed:.2f}s")
    print(f"   📊 Formatted context size: {format_token_count(formatted_tokens)} tokens")
    return result

