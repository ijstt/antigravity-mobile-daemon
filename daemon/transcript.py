"""Transcript parsing and real-time streaming for Antigravity conversations."""

import asyncio
import json
import logging
from pathlib import Path
import re
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel

from .config import CONFIG
from .sessions import SESSIONS

logger = logging.getLogger("antigravity.transcript")


class TranscriptStep(BaseModel):
    step_index: int
    source: str
    type: str
    status: str
    created_at: str
    content: Optional[str] = None
    thinking: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def from_raw_json(cls, line: str) -> Optional["TranscriptStep"]:
        try:
            raw = json.loads(line)
            content = raw.get("content")
            if content and isinstance(content, str):
                # Clean up <USER_REQUEST> markers for mobile display
                match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", content, re.DOTALL)
                if match:
                    content = match.group(1).strip()

            return cls(
                step_index=raw.get("step_index", 0),
                source=raw.get("source", "UNKNOWN"),
                type=raw.get("type", "GENERIC"),
                status=raw.get("status", "DONE"),
                created_at=raw.get("created_at", ""),
                content=content,
                thinking=raw.get("thinking"),
                tool_calls=raw.get("tool_calls"),
            )
        except Exception as e:
            logger.debug("Failed to parse transcript line: %s", e)
            return None


class TranscriptReader:
    def __init__(self, brain_dir: Optional[Path] = None):
        self.brain_dir = brain_dir or CONFIG.brain_dir

    def get_transcript_path(self, session_id: str) -> Optional[Path]:
        sdir = SESSIONS.get_session_dir(session_id)
        if not sdir:
            return None
        p = sdir / ".system_generated" / "logs" / "transcript.jsonl"
        return p if p.exists() else None

    def read_all_steps(self, session_id: str, limit: int = 500) -> List[TranscriptStep]:
        path = self.get_transcript_path(session_id)
        if not path:
            return []

        steps: List[TranscriptStep] = []
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    step = TranscriptStep.from_raw_json(line)
                    if step:
                        steps.append(step)
            if len(steps) > limit:
                steps = steps[-limit:]
        except Exception as e:
            logger.warning("Error reading transcript for %s: %s", session_id, e)
        return steps

    async def stream_new_steps(
        self, session_id: str, start_step: int = 0
    ) -> AsyncGenerator[TranscriptStep, None]:
        """Asynchronously streams new steps as they are appended to the transcript file."""
        path = self.get_transcript_path(session_id)
        if not path:
            return

        last_emitted_step = start_step - 1

        # Phase 1: Catch up with existing steps
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    step = TranscriptStep.from_raw_json(line)
                    if step and step.step_index >= start_step:
                        last_emitted_step = step.step_index
                        yield step
        except Exception as e:
            logger.warning("Error in catchup phase for %s: %s", session_id, e)

        # Phase 2: Live tailing
        while True:
            await asyncio.sleep(0.3)
            try:
                # Re-open or seek to tail new lines
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        step = TranscriptStep.from_raw_json(line)
                        if step and step.step_index > last_emitted_step:
                            last_emitted_step = step.step_index
                            yield step
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Tail polling exception: %s", e)
                await asyncio.sleep(1.0)


TRANSCRIPT = TranscriptReader()
