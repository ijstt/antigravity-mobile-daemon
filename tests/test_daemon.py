"""Unit and integration tests for Antigravity Mobile Daemon."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from daemon.app import app
from daemon.auth import AUTH
from daemon.config import CONFIG
from daemon.sessions import SessionManager
from daemon.transcript import TranscriptReader, TranscriptStep

client = TestClient(app)


def test_auth_token_properties():
    assert len(AUTH.token) >= 32
    assert AUTH.verify_token(AUTH.token) is True
    assert AUTH.verify_token("invalid_token_12345") is False
    assert AUTH.verify_token("") is False

    payload = AUTH.get_pairing_payload()
    assert payload["type"] == "antigravity-lan"
    assert "token" in payload
    assert payload["port"] == CONFIG.port


def test_qr_generation():
    ascii_qr = AUTH.render_ascii_qr()
    assert len(ascii_qr) > 50

    png_bytes = AUTH.render_png_bytes()
    assert len(png_bytes) > 100
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_health_endpoint():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "host_ip" in data
    assert data["port"] == CONFIG.port


def test_auth_endpoints():
    res_ascii = client.get("/api/v1/auth/qr")
    assert res_ascii.status_code == 200
    assert "text/plain" in res_ascii.headers["content-type"]

    res_png = client.get("/api/v1/auth/qr.png")
    assert res_png.status_code == 200
    assert res_png.headers["content-type"] == "image/png"


def test_protected_sessions_endpoint_unauthorized():
    res = client.get("/api/v1/sessions")
    assert res.status_code == 401

    res_bad = client.get("/api/v1/sessions", headers={"Authorization": "Bearer wrong_token"})
    assert res_bad.status_code == 403


def test_protected_sessions_endpoint_authorized():
    headers = {"Authorization": f"Bearer {AUTH.token}"}
    res = client.get("/api/v1/sessions", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        first = data[0]
        assert "session_id" in first
        assert "title" in first
        assert "total_steps" in first


def test_transcript_step_parser():
    raw_line = json.dumps({
        "step_index": 42,
        "source": "USER_EXPLICIT",
        "type": "USER_INPUT",
        "status": "DONE",
        "created_at": "2026-11-08T12:00:00Z",
        "content": "<USER_REQUEST>\nTest user message\n</USER_REQUEST>",
        "thinking": "Reasoning about test",
        "tool_calls": [{"name": "run_command", "args": {"cmd": "ls"}}],
    })

    step = TranscriptStep.from_raw_json(raw_line)
    assert step is not None
    assert step.step_index == 42
    assert step.content == "Test user message"
    assert step.thinking == "Reasoning about test"
    assert step.tool_calls[0]["name"] == "run_command"


def test_active_session_resolution(tmp_path):
    mock_brain = tmp_path / "mock_brain"
    mock_session = mock_brain / "session-123"
    log_dir = mock_session / ".system_generated" / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "transcript.jsonl").write_text('{"step_index":0,"source":"USER","content":"hi"}\n')

    sm = SessionManager(brain_dir=mock_brain)
    active_id = sm.get_active_session_id()
    assert active_id == "session-123"
    sdir = sm.get_session_dir(active_id)
    assert sdir is not None
    assert sdir.exists()


def test_system_telemetry_endpoint():
    headers = {"Authorization": f"Bearer {AUTH.token}"}
    res = client.get("/api/v1/system/telemetry", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "cpu_load_1m" in data
    assert "ram_percent" in data
    assert "ram_used_mb" in data
    assert "uptime_seconds" in data


def test_remote_control_endpoint():
    headers = {"Authorization": f"Bearer {AUTH.token}"}
    res = client.get("/api/v1/system/remote-control", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "enabled" in data
    assert "device_name" in data
    assert isinstance(data["device_name"], str)
    if data["enabled"]:
        assert data["relay_id"] is not None
        assert "antigravity.google.com" in data["url"]


