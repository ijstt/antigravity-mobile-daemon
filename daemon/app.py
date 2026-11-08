"""FastAPI REST and WebSocket application for Antigravity Mobile Daemon."""

from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .auth import AUTH, verify_bearer_token
from .config import CONFIG
from .discovery import DISCOVERY
from .sessions import ArtifactMetadata, SESSIONS, SessionMetadata
from .transcript import TRANSCRIPT, TranscriptStep

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("antigravity.daemon")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Antigravity Mobile Daemon on port %d...", CONFIG.port)
    DISCOVERY.start()
    yield
    logger.info("Stopping Antigravity Mobile Daemon...")
    DISCOVERY.stop()


app = FastAPI(
    title="Antigravity Mobile Gateway",
    version=CONFIG.version,
    description="Edge LAN gateway for Google Antigravity mobile interaction",
    lifespan=lifespan,
)

# Enable CORS for local network and dev tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PromptRequest(BaseModel):
    prompt: str
    client_id: Optional[str] = "mobile-android"


class HealthResponse(BaseModel):
    status: str
    version: str
    host_ip: str
    port: int
    active_session_id: Optional[str]


@app.get("/api/v1/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        version=CONFIG.version,
        host_ip=CONFIG.local_ip,
        port=CONFIG.port,
        active_session_id=SESSIONS.get_active_session_id(),
    )


@app.get("/api/v1/auth/qr")
async def get_ascii_qr():
    """Returns ASCII representation of the pairing QR code."""
    return Response(content=AUTH.render_ascii_qr(), media_type="text/plain")


@app.get("/api/v1/auth/qr.png")
async def get_png_qr():
    """Returns PNG image of the pairing QR code."""
    return Response(content=AUTH.render_png_bytes(), media_type="image/png")


@app.get("/api/v1/download/apk")
async def download_apk():
    """Serves the latest compiled Android Companion APK for direct local download."""
    apk_path = Path("/tmp/antigravity-companion-apk/app-debug.apk")
    if not apk_path.exists():
        raise HTTPException(status_code=404, detail="APK not found on host. Run deploy-to-phone.sh first.")
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(apk_path),
        filename="antigravity-companion.apk",
        media_type="application/vnd.android.package-archive",
    )


@app.get("/api/v1/sessions", response_model=List[SessionMetadata])
async def list_sessions(token: str = Depends(verify_bearer_token)):
    return SESSIONS.list_sessions()


@app.get("/api/v1/sessions/active", response_model=Optional[SessionMetadata])
async def get_active_session(token: str = Depends(verify_bearer_token)):
    active_id = SESSIONS.get_active_session_id()
    if not active_id:
        return None
    for s in SESSIONS.list_sessions():
        if s.session_id == active_id:
            return s
    return None


@app.get("/api/v1/sessions/{session_id}/transcript", response_model=List[TranscriptStep])
async def get_transcript(
    session_id: str,
    limit: int = Query(default=300, ge=1, le=2000),
    token: str = Depends(verify_bearer_token),
):
    if not SESSIONS.get_session_dir(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return TRANSCRIPT.read_all_steps(session_id, limit=limit)


@app.get("/api/v1/sessions/{session_id}/artifacts", response_model=List[ArtifactMetadata])
async def list_artifacts(session_id: str, token: str = Depends(verify_bearer_token)):
    if not SESSIONS.get_session_dir(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return SESSIONS.list_artifacts(session_id)


@app.get("/api/v1/sessions/{session_id}/artifacts/{artifact_name}")
async def get_artifact(session_id: str, artifact_name: str, token: str = Depends(verify_bearer_token)):
    content = SESSIONS.get_artifact(session_id, artifact_name)
    if content is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return Response(content=content, media_type="text/markdown")


@app.get("/api/v1/system/telemetry")
async def get_telemetry(token: str = Depends(verify_bearer_token)):
    from .telemetry import get_system_telemetry
    return get_system_telemetry()


@app.get("/api/v1/system/remote-control")
async def get_remote_control(token: str = Depends(verify_bearer_token)):
    from .telemetry import get_remote_control_info
    return get_remote_control_info()



@app.get("/api/v1/sessions/{session_id}/tasks")
async def get_tasks(session_id: str, token: str = Depends(verify_bearer_token)):
    from .telemetry import list_session_tasks
    if not SESSIONS.get_session_dir(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return list_session_tasks(session_id)


@app.get("/api/v1/sessions/{session_id}/tasks/{task_id}/log")
async def get_task_log(session_id: str, task_id: str, token: str = Depends(verify_bearer_token)):
    from .telemetry import get_task_full_log
    log_content = get_task_full_log(session_id, task_id)
    if log_content is None:
        raise HTTPException(status_code=404, detail="Task log not found")
    return Response(content=log_content, media_type="text/plain")


@app.post("/api/v1/sessions/{session_id}/prompt")
async def inject_prompt(
    session_id: str,
    req: PromptRequest,
    token: str = Depends(verify_bearer_token),
):
    sdir = SESSIONS.get_session_dir(session_id)
    if not sdir:
        raise HTTPException(status_code=404, detail="Session not found")

    queue_file = sdir / "mobile_prompt_queue.jsonl"
    entry = {
        "timestamp": json.dumps({"$now": True}),
        "client_id": req.client_id,
        "prompt": req.prompt,
        "status": "QUEUED",
    }
    with open(queue_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    logger.info("Prompt enqueued for session %s from %s: %s", session_id, req.client_id, req.prompt[:60])
    return {"status": "enqueued", "session_id": session_id, "prompt_length": len(req.prompt)}


@app.websocket("/ws/sessions/{session_id}")
async def websocket_session_stream(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(default=None),
):
    # Verify token
    if not token or not AUTH.verify_token(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Check session
    if session_id == "live":
        active = SESSIONS.get_active_session_id()
        if not active:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return
        session_id = active

    if not SESSIONS.get_session_dir(session_id):
        await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
        return

    await websocket.accept()
    logger.info("WebSocket connected for session: %s", session_id)

    await websocket.send_json({
        "type": "CONNECTED",
        "session_id": session_id,
        "version": CONFIG.version,
    })

    # Start streaming transcript events
    stream_task = None

    async def sender():
        async for step in TRANSCRIPT.stream_new_steps(session_id):
            await websocket.send_json({
                "type": "STEP",
                "session_id": session_id,
                "data": step.model_dump(),
            })

    async def receiver():
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                mtype = msg.get("type")
                if mtype == "PING":
                    await websocket.send_json({"type": "PONG"})
                elif mtype == "PROMPT":
                    prompt_text = msg.get("content", "")
                    if prompt_text:
                        sdir = SESSIONS.get_session_dir(session_id)
                        if sdir:
                            queue_file = sdir / "mobile_prompt_queue.jsonl"
                            entry = {
                                "client_id": "mobile-websocket",
                                "prompt": prompt_text,
                                "status": "QUEUED",
                            }
                            with open(queue_file, "a", encoding="utf-8") as f:
                                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                            await websocket.send_json({"type": "PROMPT_ACK", "status": "queued"})
            except Exception as e:
                logger.debug("WS receiver exception: %s", e)

    import asyncio
    sender_task = asyncio.create_task(sender())
    receiver_task = asyncio.create_task(receiver())

    try:
        done, pending = await asyncio.wait(
            [sender_task, receiver_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from %s", session_id)
    except Exception as e:
        logger.warning("WebSocket error: %s", e)
    finally:
        sender_task.cancel()
        receiver_task.cancel()
