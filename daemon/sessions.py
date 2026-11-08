"""Session indexing and metadata management for Antigravity conversations."""

import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from .config import CONFIG

logger = logging.getLogger("antigravity.sessions")


class SessionMetadata(BaseModel):
    session_id: str
    last_modified: float
    total_steps: int
    title: str
    artifact_count: int
    is_active: bool = False


class ArtifactMetadata(BaseModel):
    name: str
    size_bytes: int
    last_modified: float
    is_markdown: bool


class SessionManager:
    def __init__(self, brain_dir: Optional[Path] = None):
        self.brain_dir = brain_dir or CONFIG.brain_dir

    def list_sessions(self) -> List[SessionMetadata]:
        sessions: List[SessionMetadata] = []
        if not self.brain_dir.exists():
            return sessions

        active_id = self.get_active_session_id()

        for path in self.brain_dir.iterdir():
            if not path.is_dir() or path.name.startswith("."):
                continue

            transcript_path = path / ".system_generated" / "logs" / "transcript.jsonl"
            if not transcript_path.exists():
                continue

            try:
                stat = transcript_path.stat()
                last_modified = stat.st_mtime
                step_count = 0
                title = "Untitled Conversation"

                # Read first line for title and count steps
                with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f):
                        step_count += 1
                        if i == 0:
                            try:
                                obj = json.loads(line)
                                raw_content = obj.get("content", "")
                                # Strip <USER_REQUEST> tags if present
                                match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", raw_content, re.DOTALL)
                                if match:
                                    clean = match.group(1).strip()
                                else:
                                    clean = raw_content.strip()
                                first_line = clean.split("\n")[0].strip()
                                if first_line:
                                    title = (first_line[:75] + "...") if len(first_line) > 75 else first_line
                            except Exception:
                                pass

                artifacts = self.list_artifacts(path.name)

                sessions.append(
                    SessionMetadata(
                        session_id=path.name,
                        last_modified=last_modified,
                        total_steps=step_count,
                        title=title,
                        artifact_count=len(artifacts),
                        is_active=(path.name == active_id),
                    )
                )
            except Exception as e:
                logger.warning("Error reading session %s: %s", path.name, e)

        # Sort descending by last modified
        sessions.sort(key=lambda s: s.last_modified, reverse=True)
        return sessions

    def get_active_session_id(self) -> Optional[str]:
        """Returns the conversation ID of the most recently modified transcript."""
        best_time = 0.0
        best_id = None
        if not self.brain_dir.exists():
            return None

        for path in self.brain_dir.iterdir():
            if not path.is_dir() or path.name.startswith("."):
                continue
            transcript = path / ".system_generated" / "logs" / "transcript.jsonl"
            if transcript.exists():
                mtime = transcript.stat().st_mtime
                if mtime > best_time:
                    best_time = mtime
                    best_id = path.name
        return best_id

    def get_session_dir(self, session_id: str) -> Optional[Path]:
        p = self.brain_dir / session_id
        if p.exists() and p.is_dir():
            return p
        return None

    def list_artifacts(self, session_id: str) -> List[ArtifactMetadata]:
        sdir = self.get_session_dir(session_id)
        if not sdir:
            return []

        artifacts: List[ArtifactMetadata] = []
        for f in sdir.iterdir():
            if f.is_file() and not f.name.startswith("."):
                artifacts.append(
                    ArtifactMetadata(
                        name=f.name,
                        size_bytes=f.stat().st_size,
                        last_modified=f.stat().st_mtime,
                        is_markdown=f.suffix.lower() == ".md",
                    )
                )
        artifacts.sort(key=lambda a: a.last_modified, reverse=True)
        return artifacts

    def get_artifact(self, session_id: str, artifact_name: str) -> Optional[str]:
        sdir = self.get_session_dir(session_id)
        if not sdir:
            return None
        # Prevent path traversal
        clean_name = Path(artifact_name).name
        target = sdir / clean_name
        if target.exists() and target.is_file():
            return target.read_text(encoding="utf-8", errors="replace")
        return None


SESSIONS = SessionManager()
