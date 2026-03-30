from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from .workspace import Workspace

logger = logging.getLogger(__name__)
router = APIRouter()

SYSTEM_PROMPT = """
You are Golem, an AI agent that writes FemCAD Script (FCS) files to create
parametric 3D building models for HiStruct.

FCS rules you must follow:
- Every project needs a main.fcs that defines a GClass named "main" as the entry point
- Use GBlock and GClass for geometry hierarchy
- Parameters are declared as: name := value
- Import other files with: import "filename.fcs"
- Geometry: use Fcs.Box(width, height, depth), Fcs.Prism(), Fcs.Translate(), etc.
- Materials: Fcs.Material(color := [r, g, b]) where rgb are 0.0-1.0
- Keep each file focused on one element (house.fcs, roof.fcs, garage.fcs, main.fcs)

Respond with ONLY a JSON object, no markdown, no explanation. Format:
{
  "files": {
    "house.fcs": "... fcs content ...",
    "main.fcs": "... fcs content ..."
  },
  "chat_message": "one sentence describing what you built or changed"
}
"""


class GenerateRequest(BaseModel):
    """Request model for /api/generate."""

    message: str
    session_id: str
    files: dict[str, str] = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    """Response model for /api/generate."""

    files: dict[str, str]
    hiscene: dict | None
    viewer_url: str | None
    chat_message: str
    error: str | None


async def _get_user_for_generate(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
) -> Dict[str, str]:
    """Resolve user by calling web_app._get_user_optional lazily at request time."""
    from .web_app import _get_user_optional

    return await _get_user_optional(credentials)


def _extract_json_object(raw: str) -> dict[str, Any]:
    """Parse JSON object from model output with simple fence/object recovery."""
    text = raw.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("Top-level JSON is not an object")
    except Exception:
        # Try to recover from accidental wrapping text.
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            candidate = text[start : end + 1]
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        raise


def _invoke_generate_payload(rag_llm: Any, user_message: str) -> dict[str, Any]:
    """Call the model and parse the JSON payload with one retry."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    parse_error: Optional[Exception] = None
    for _ in range(2):
        result = rag_llm.invoke(messages)
        content = result.content if hasattr(result, "content") else str(result)
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        try:
            return _extract_json_object(str(content))
        except Exception as exc:
            parse_error = exc
            logger.warning("Failed to parse generate payload: %s", exc)
            continue

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="LLM returned unparseable response",
    ) from parse_error


def _normalize_llm_payload(payload: dict[str, Any]) -> tuple[dict[str, str], str]:
    """Normalize and validate files/chat_message fields from model payload."""
    files = payload.get("files")
    chat_message = payload.get("chat_message")

    if not isinstance(files, dict):
        raise HTTPException(status_code=500, detail="LLM returned invalid files payload")

    normalized_files: dict[str, str] = {}
    for filename, content in files.items():
        if not isinstance(filename, str):
            continue
        normalized_files[filename] = content if isinstance(content, str) else str(content)

    if not normalized_files:
        raise HTTPException(status_code=500, detail="LLM returned empty files payload")

    if not isinstance(chat_message, str) or not chat_message.strip():
        chat_message = "I updated the FCS files for your request."

    return normalized_files, chat_message.strip()


@router.post("/api/generate", response_model=GenerateResponse)
async def generate(
    request: GenerateRequest,
    user: Dict[str, str] = Depends(_get_user_for_generate),
) -> GenerateResponse:
    """Generate FCS files, compile them to hiScene when available, and return viewer URL."""
    del user  # auth dependency enforces access; user is not otherwise needed.

    from .web_app import rag_llm

    if rag_llm is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Generation model not ready.",
        )

    base_user_message = (
        f"User request: {request.message}\n\n"
        "Current files (empty if first request):\n"
        f"{json.dumps(request.files, indent=2) if request.files else 'none'}"
    )

    payload = _invoke_generate_payload(rag_llm=rag_llm, user_message=base_user_message)
    files_written, chat_message = _normalize_llm_payload(payload)

    workspace = Workspace(session_id=request.session_id)
    workspace.write_files(files_written)

    hiscene, fli_error = workspace.run_fli()
    viewer_url: str | None = None
    response_error: str | None = None

    if hiscene is not None:
        viewer_url = workspace.to_viewer_url(hiscene)
    elif fli_error and "not available" in fli_error.lower():
        # Local dev without fli.exe should not surface as an API error.
        fli_error = None
    elif fli_error:
        fix_user_message = (
            "The FCS files produced this error when compiled:\n"
            f"{fli_error}\n\n"
            f"Original request: {request.message}\n"
            "Current files:\n"
            f"{json.dumps(files_written, indent=2)}\n\n"
            "Fix the files and return the same JSON format."
        )
        fix_payload = _invoke_generate_payload(rag_llm=rag_llm, user_message=fix_user_message)
        fixed_files, fixed_chat_message = _normalize_llm_payload(fix_payload)
        workspace.write_files(fixed_files)
        files_written = fixed_files
        chat_message = fixed_chat_message

        hiscene, second_error = workspace.run_fli()
        if hiscene is not None:
            viewer_url = workspace.to_viewer_url(hiscene)
            response_error = None
        else:
            response_error = second_error

    return GenerateResponse(
        files=files_written,
        hiscene=hiscene,
        viewer_url=viewer_url,
        chat_message=chat_message,
        error=response_error,
    )
