from __future__ import annotations

import base64
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Workspace:
    """Manage an isolated per-session workspace of FCS files."""

    def __init__(self, session_id: str, base_dir: Optional[Path] = None) -> None:
        self.session_id = session_id
        self.base_dir = base_dir or (PROJECT_ROOT / "workspaces")
        self.path = self.base_dir / session_id[:16]
        self.path.mkdir(parents=True, exist_ok=True)

    def write_files(self, files: dict[str, str]) -> None:
        """Write filename/content pairs into the workspace."""
        self.path.mkdir(parents=True, exist_ok=True)
        for filename, content in files.items():
            if not filename.endswith(".fcs"):
                raise ValueError(f"Only .fcs files are allowed: {filename}")
            target = self.path / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def read_files(self) -> dict[str, str]:
        """Read all .fcs files in the workspace as filename/content pairs."""
        if not self.path.exists():
            return {}

        files: dict[str, str] = {}
        for fcs_path in sorted(self.path.glob("*.fcs")):
            files[fcs_path.name] = fcs_path.read_text(encoding="utf-8")
        return files

    def main_fcs_path(self) -> Optional[Path]:
        """Return main.fcs path if present, otherwise the first .fcs file."""
        if not self.path.exists():
            return None

        main_path = self.path / "main.fcs"
        if main_path.exists():
            return main_path

        fcs_files = sorted(self.path.glob("*.fcs"))
        return fcs_files[0] if fcs_files else None

    def run_fli(self) -> tuple[dict | None, str | None]:
        """Run fli.exe --dump-scene against the workspace entry file."""
        main_path = self.main_fcs_path()
        if main_path is None:
            return None, "No .fcs files found"

        fli_exe = os.getenv("FLI_EXE_PATH", "fli.exe")
        if not fli_exe or fli_exe.strip() == "":
            return None, "fli.exe not available"

        try:
            result = subprocess.run(
                [fli_exe, "--dump-scene", str(main_path)],
                cwd=self.path,
                check=False,
                timeout=30,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return None, "fli.exe not available"
        except subprocess.TimeoutExpired:
            return None, "fli.exe timed out after 30 seconds"
        except Exception as exc:
            logger.exception("Unexpected fli.exe error")
            return None, f"fli.exe failed: {exc}"

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            detail = stderr or stdout or f"exit code {result.returncode}"
            return None, f"fli.exe failed: {detail}"

        output = (result.stdout or "").strip()
        if not output:
            return None, "fli.exe failed: empty output"

        try:
            return json.loads(output), None
        except json.JSONDecodeError as exc:
            return None, f"fli.exe failed: invalid JSON output ({exc})"

    def to_viewer_url(self, hiscene: dict) -> str:
        """Convert hiScene JSON to viewer URL with base64url fragment."""
        payload = json.dumps(hiscene, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
        return f"https://viewer.histruct.com/#{encoded}"

    def cleanup(self) -> None:
        """Remove workspace directory and all contents."""
        shutil.rmtree(self.path, ignore_errors=True)
