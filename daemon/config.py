"""Configuration management for Antigravity Mobile Daemon."""

from dataclasses import dataclass
import os
from pathlib import Path
import socket


@dataclass
class DaemonConfig:
    host: str = "0.0.0.0"
    port: int = 8767
    brain_dir: Path = Path(os.path.expanduser("~/.gemini/antigravity/brain"))
    config_dir: Path = Path(os.path.expanduser("~/.config/antigravity-mobile"))
    token_file: Path = Path(os.path.expanduser("~/.config/antigravity-mobile/token.txt"))
    mdns_service_name: str = "Antigravity Gateway"
    mdns_service_type: str = "_antigravity._tcp.local."
    version: str = "1.0.0"

    def __post_init__(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.brain_dir.exists():
            self.brain_dir.mkdir(parents=True, exist_ok=True)

    @property
    def local_ip(self) -> str:
        """Determines best outbound local IP address for LAN connection."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Does not need to be reachable, purely for kernel routing table lookup
            try:
                s.connect(("10.255.255.255", 1))
                ip = s.getsockname()[0]
            except Exception:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip


CONFIG = DaemonConfig()
