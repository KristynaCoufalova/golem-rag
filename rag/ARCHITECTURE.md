# Golem RAG Architecture

This document describes the architecture of the Golem RAG (Retrieval-Augmented Generation) system. Use this as a reference guide for future RAG development.

## System Architecture Overview

```
┌───────────────────────────────────────────────────────────────┐
│                       USER + UI                               │
│                                                                │
│  - Question: "How do I create a beam with report?"            │
│                                                                │
│  - Session ID (for memory)                                    │
└───────────────┬───────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│        1. CONVERSATION MEMORY + QUERY ENHANCER                │
├───────────────────────────────────────────────────────────────┤
│  - Input: (session_id, user_question)                         │
│  - Memory store:                                              │
│      • last N turns                                           │
│      • short summary of older context                         │
│  - Output: enhanced_question                                  │
│    e.g. "User previously asked about beams & hinges. Now      │
│         asks how to create a beam with report outputs..."     │
└───────────────┬───────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│             2. DOMAIN CLASSIFIER (FemCAD pipeline)            │
├───────────────────────────────────────────────────────────────┤
│  - Uses FemCAD mental model:                                  │
│      • geometry                                               │
│      • analysis (FEM, beams, loads, hinges…)                  │
│      • reporting (Fcs.Reporting.*, HTML, tables…)             │
│      • component (HiStruct components, UI, parameters…)       │
│  - Output: domain_preference = [ "analysis", "reporting" ]    │
└───────────────┬───────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│   3. TIER 0: FEMCAD FUNDAMENTALS (NO RETRIEVAL, ALWAYS ON)    │
├───────────────────────────────────────────────────────────────┤
│  - femcad_basics_compact.md   (short, always injected)        │
│  - femcad_basics.md           (longer)                        │
│      • included when:                                          │
│         - question is about syntax/fundamentals, OR           │
│         - higher tiers are weak / low scores                  │
│  - Treated as "built-in system context"                       │
└───────────────┬───────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│  4. TIERED, DOMAIN-AWARE RETRIEVAL MANAGER                    │
│     (semantics + FemCAD structure)                            │
├───────────────────────────────────────────────────────────────┤
│  Input:                                                        │
│    - enhanced_question                                         │
│    - domain_preference (e.g. ["analysis","reporting"])         │
│    - desired k + thresholds per tier                           │
│                                                                │
│  Knowledge layer (all chunks carry metadata):                  │
│    ChunkMetadata = {                                           │
│      db: "code" | "docs" | "lessons" |                         │
│          "templates" | "api_source" | "unit_tests",            │
│      domain: "geometry" | "analysis" |                         │
│              "reporting" | "component",                        │
│      subdomain: e.g. "vertex" | "curve" | "beam" | "hinge" |   │
│                 "load" | "report_table" | "component_ui",      │
│      path: "code-examples/.../BeamStandard.fcs",               │
│      ...                                                       │
│    }                                                           │
│                                                                │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ TIER 1 – PRIMARY (high quality, first attempt)           │ │
│  │  • vectordb_code, vectordb_docs                          │ │
│  │  • Filter / boost by domain_preference                   │ │
│  │  • Example: only chunks where domain ∈ {"analysis"}      │ │
│  │    when question is about beams                          │ │
│  │  • If enough high-score hits ⇒ STOP                      │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ TIER 2 – SECONDARY (lessons, templates)                  │ │
│  │  • vectordb_lessons, vectordb_templates                  │ │
│  │  • Still prefer matching domains                         │ │
│  │  • Used only if Tier 1 is weak                           │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ TIER 3 – EXPERT (last resort)                            │ │
│  │  • vectordb_api_source, vectordb_unit_tests              │ │
│  │  • Lower thresholds (0.5), still domain-aware            │ │
│  │  • Pulled in only when we're "desperate" for context     │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                │
│  Output: retrieved_chunks grouped by tier + domain            │
└───────────────┬───────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│                     6. LLM (Azure gpt-5-mini)                  │
├───────────────────────────────────────────────────────────────┤
│  - System prompt: "You are Golem..."                 │
│  - Input:                                                     │
│      • structured context from assembler                      │
│      • enhanced_question                                      │
│  - Output:                                                    │
│      • Answer structured along FemCAD architecture:           │
│          1. Geometry: vertices, curves, gblocks               │
│          2. Analysis: materials, cross_section, beam, mesh    │
│          3. Reporting: Fcs.Reporting.* examples               │
│          4. Component: how to wrap as HiStruct component      │
└───────────────┬───────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│                     7. RESPONSE + LOGS                        │
├───────────────────────────────────────────────────────────────┤
│  - UI shows:                                                  │
│      • Final answer                                           │
│      • (Optionally) "Sources used" by tier + domain           │
│  - Logs store:                                                │
│      • which tiers were used                                  │
│      • domain_preference                                      │
│      • retrieved chunk ids                                    │
└───────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Conversation Memory + Query Enhancer
- **Purpose**: Maintains conversation context across turns
- **Implementation**: `conversation_memory.py`
- **Features**:
  - Stores last N conversation turns
  - Maintains short summary of older context
  - Enhances queries with historical context

### 2. Domain Classifier
- **Purpose**: Identifies relevant FemCAD domains for the query
- **Domains**:
  - `geometry`: Vertices, curves, gblocks
  - `analysis`: FEM, beams, loads, hinges
  - `reporting`: Fcs.Reporting.*, HTML, tables
  - `component`: HiStruct components, UI, parameters
- **Output**: List of preferred domains (e.g., `["analysis", "reporting"]`)

### 3. Tier 0: FemCAD Fundamentals
- **Purpose**: Always-included foundational knowledge
- **Files**:
  - `femcad_basics_compact.md` (always injected)
  - `femcad_basics.md` (included when needed)
- **Usage**: Treated as built-in system context, no retrieval needed

### 4. Tiered, Domain-Aware Retrieval Manager
- **Purpose**: Retrieves relevant chunks from multiple knowledge sources
- **Tiers**:
  - **Tier 1 (Primary)**: `vectordb_code`, `vectordb_docs`
    - High quality, first attempt
    - Filtered/boosted by domain preference
    - Stops if enough high-score hits found
  - **Tier 2 (Secondary)**: `vectordb_lessons`, `vectordb_templates`
    - Used only if Tier 1 is weak
    -    5. CONTEXT ASSEMBLER (FemCAD-structured)             │
├───────────────────────────────────────────────────────────────┤
│  Builds the final prompt context:                             │
│    1) Tier 0 → FemCAD basics (compact, maybe full)            │
│    2) Conversation memory summary                             │
│    3) Retrieved chunks, grouped and tagged, e.g.:             │
│         - "Tier 1 / analysis / beams"                         │
│         - "Tier 2 / geometry / gblocks"                       │
│         - "Tier 3 / analysis / source code"                   │
│                                                                │
│  System guidance for the LLM:                                 │
│    • Follow FemCAD pipeline when relevant:                    │
│        Geometry → Analysis → Reporting → Component            │
│    • Prefer curated examples over raw source code             │
│    • Be explicit about assumptions and beam types             │
└───────────────┬───────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│      Still domain-aware
  - **Tier 3 (Expert)**: `vectordb_api_source`, `vectordb_unit_tests`
    - Last resort with lower thresholds (~0.5)
    - Domain-aware but more permissive

### 5. Context Assembler
- **Purpose**: Builds structured prompt context for the LLM
- **Structure**:
  1. Tier 0: FemCAD basics
  2. Conversation memory summary
  3. Retrieved chunks (grouped by tier + domain)
- **Guidance**: Instructs LLM to follow FemCAD pipeline (Geometry → Analysis → Reporting → Component)

### 6. LLM (Azure GPT-5-mini)
- **Purpose**: Generates final answer based on structured context
- **Input**: Enhanced question + structured context
- **Output**: Answer structured along FemCAD architecture

### 7. Response + Logs
- **Purpose**: Delivers answer and tracks system behavior
- **Features**:
  - Shows final answer to user
  - Optionally shows sources used (by tier + domain)
  - Logs: tiers used, domain preferences, retrieved chunk IDs

## Chunk Metadata Schema

All chunks in the knowledge base should carry the following metadata:

```python
ChunkMetadata = {
    db: "code" | "docs" | "lessons" | "templates" | "api_source" | "unit_tests",
    domain: "geometry" | "analysis" | "reporting" | "component",
    subdomain: str,  # e.g. "vertex", "curve", "beam", "hinge", "load", 
                     #      "report_table", "component_ui"
    path: str,       # e.g. "code-examples/.../BeamStandard.fcs"
    # ... other metadata fields
}
```

## FemCAD Pipeline

The system follows the FemCAD mental model:

1. **Geometry**: Vertices, curves, gblocks
2. **Analysis**: Materials, cross_section, beam, mesh
3. **Reporting**: Fcs.Reporting.* examples
4. **Component**: How to wrap as HiStruct component

## Development Guidelines

When implementing or modifying RAG components:

1. **Follow the tiered retrieval approach**: Always try Tier 1 first, fall back to Tier 2, then Tier 3
2. **Respect domain preferences**: Filter and boost chunks based on domain classification
3. **Maintain conversation context**: Use the memory system to enhance queries
4. **Structure responses**: Organize answers along the FemCAD pipeline when relevant
5. **Log everything**: Track which tiers, domains, and chunks were used for debugging

## Related Files

- `conversation_memory.py`: Conversation memory implementation
- `rag.py`: Enhanced RAG implementation (combines code and docs retrieval)
- `web_app.py`: FastAPI web interface

