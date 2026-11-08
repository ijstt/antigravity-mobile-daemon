"""Host telemetry and background task monitoring for Antigravity Mobile Gateway."""

from pathlib import Path
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from .config import CONFIG
from .sessions import SESSIONS


class SystemTelemetry(BaseModel):
    cpu_load_1m: float
    cpu_load_5m: float
    ram_used_mb: int
    ram_total_mb: int
    ram_percent: float
    battery_percent: Optional[int] = None
    battery_status: Optional[str] = None
    uptime_seconds: float
    timestamp: float


class TaskInfo(BaseModel):
    task_id: str
    log_size_bytes: int
    last_modified: float
    log_snippet: str


def get_system_telemetry() -> SystemTelemetry:
    # CPU Load
    cpu_1m, cpu_5m = 0.0, 0.0
    try:
        with open("/proc/loadavg", "r") as f:
            parts = f.read().split()
            cpu_1m, cpu_5m = float(parts[0]), float(parts[1])
    except Exception:
        pass

    # RAM
    ram_total_mb, ram_avail_mb = 0, 0
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    ram_total_mb = int(line.split()[1]) // 1024
                elif line.startswith("MemAvailable:"):
                    ram_avail_mb = int(line.split()[1]) // 1024
    except Exception:
        pass
    ram_used_mb = max(0, ram_total_mb - ram_avail_mb)
    ram_percent = round((ram_used_mb / ram_total_mb * 100), 1) if ram_total_mb > 0 else 0.0

    # Battery
    bat_pct: Optional[int] = None
    bat_stat: Optional[str] = None
    try:
        for p in Path("/sys/class/power_supply").glob("BAT*"):
            cap_file = p / "capacity"
            stat_file = p / "status"
            if cap_file.exists():
                bat_pct = int(cap_file.read_text().strip())
            if stat_file.exists():
                bat_stat = stat_file.read_text().strip()
            break
    except Exception:
        pass

    # Uptime
    uptime = 0.0
    try:
        with open("/proc/uptime", "r") as f:
            uptime = float(f.read().split()[0])
    except Exception:
        pass

    return SystemTelemetry(
        cpu_load_1m=cpu_1m,
        cpu_load_5m=cpu_5m,
        ram_used_mb=ram_used_mb,
        ram_total_mb=ram_total_mb,
        ram_percent=ram_percent,
        battery_percent=bat_pct,
        battery_status=bat_stat,
        uptime_seconds=uptime,
        timestamp=time.time(),
    )


def list_session_tasks(session_id: str) -> List[TaskInfo]:
    sdir = SESSIONS.get_session_dir(session_id)
    if not sdir:
        return []

    tasks_dir = sdir / ".system_generated" / "tasks"
    if not tasks_dir.exists():
        return []

    results: List[TaskInfo] = []
    for log_file in tasks_dir.glob("task-*.log"):
        stat = log_file.stat()
        task_id = log_file.stem
        snippet = ""
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                snippet = "".join(lines[-5:]) if lines else "[Empty Log]"
        except Exception:
            snippet = "[Read Error]"

        results.append(
            TaskInfo(
                task_id=task_id,
                log_size_bytes=stat.st_size,
                last_modified=stat.st_mtime,
                log_snippet=snippet.strip(),
            )
        )

    results.sort(key=lambda t: t.last_modified, reverse=True)
    return results


def get_task_full_log(session_id: str, task_id: str) -> Optional[str]:
    sdir = SESSIONS.get_session_dir(session_id)
    if not sdir:
        return None
    # sanitize task_id
    clean_id = Path(task_id).name
    log_file = sdir / ".system_generated" / "tasks" / f"{clean_id}.log"
    if log_file.exists():
        return log_file.read_text(encoding="utf-8", errors="replace")
    return None


class RemoteControlInfo(BaseModel):
    enabled: bool
    device_name: str
    relay_id: Optional[str] = None
    email: Optional[str] = None
    url: Optional[str] = None


def get_remote_control_info() -> RemoteControlInfo:
    """Extracts the active Google Antigravity Remote Control relay session from language server logs."""
    import re
    import socket
    import urllib.parse

    log_path = Path.home() / ".config" / "Antigravity" / "logs" / "language_server.log"
    relay_id: Optional[str] = None

    if log_path.exists():
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-2000:]
                for line in reversed(lines):
                    m = re.search(r"remote-control-([a-zA-Z0-9\-]+-v[0-9]+)", line)
                    if m:
                        relay_id = m.group(1)
                        break
        except Exception:
            pass

    device_name = socket.gethostname()

    if not relay_id:
        return RemoteControlInfo(
            enabled=False,
            device_name=device_name,
            relay_id=None,
            email=None,
            url=None,
        )

    continue_url = f"https://antigravity.google.com/r/{relay_id}"
    return RemoteControlInfo(
        enabled=True,
        device_name=device_name,
        relay_id=relay_id,
        email=None,
        url=continue_url,
    )

