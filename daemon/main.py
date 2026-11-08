"""CLI entrypoint for Antigravity Mobile Gateway Daemon."""

import argparse
import sys
import uvicorn

from .auth import AUTH
from .config import CONFIG


def parse_args():
    parser = argparse.ArgumentParser(description="Antigravity Mobile Gateway Daemon")
    parser.add_argument("--host", default=CONFIG.host, help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=CONFIG.port, help="Bind port (default: 8767)")
    parser.add_argument("--qr", action="store_true", help="Print terminal pairing QR code and exit")
    parser.add_argument("--token", action="store_true", help="Print authorization token and exit")
    parser.add_argument("--info", action="store_true", help="Print gateway connection info and exit")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.token:
        print(AUTH.token)
        sys.exit(0)

    if args.info:
        print(f"Antigravity Mobile Gateway v{CONFIG.version}")
        print(f"Local IP: {CONFIG.local_ip}")
        print(f"Port: {CONFIG.port}")
        print(f"Token: {AUTH.token}")
        print(f"Pairing JSON: {AUTH.get_pairing_json_string()}")
        sys.exit(0)

    if args.qr:
        print("=== Antigravity Mobile QR Pairing ===")
        print(AUTH.render_ascii_qr())
        print(f"Endpoint: http://{CONFIG.local_ip}:{args.port}")
        print(f"Token: {AUTH.token}")
        sys.exit(0)

    print("==================================================================")
    print(f"  Antigravity Mobile Gateway v{CONFIG.version} Starting...")
    print(f"  LAN Address: http://{CONFIG.local_ip}:{args.port}")
    print(f"  WebSocket:   ws://{CONFIG.local_ip}:{args.port}/ws/sessions/live")
    print(f"  QR Web View: http://{CONFIG.local_ip}:{args.port}/api/v1/auth/qr.png")
    print("==================================================================")
    print("Scan this QR code with the Antigravity Android Companion App:")
    print(AUTH.render_ascii_qr())
    print("==================================================================")

    CONFIG.host = args.host
    CONFIG.port = args.port

    uvicorn.run(
        "daemon.app:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
