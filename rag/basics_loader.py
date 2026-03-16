"""
Loader for FemCAD basics document.
"""

from pathlib import Path
from langchain_core.documents import Document

from .config import PROJECT_ROOT
from .utils import timing_context


def load_femcad_basics(basics_path: str) -> Document:
    """Load FemCAD basics as a Document"""
    path = Path(basics_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Basics file not found: {basics_path}\n"
            f"Expected location: {PROJECT_ROOT / 'data' / 'femcad_basics_compact.md'}"
        )
    
    print(f"📘 Loading FemCAD basics from: {basics_path}")
    with timing_context("Loading basics file"):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    
    basics_doc = Document(
        page_content=content,
        metadata={
            "source": "femcad_fundamentals",
            "type": "always_included",
            "priority": "highest"
        }
    )
    
    print(f"   ✓ Loaded {len(content)} characters")
    return basics_doc

