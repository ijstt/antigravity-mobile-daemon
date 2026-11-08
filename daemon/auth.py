"""Authentication and QR code pairing for Antigravity Mobile Daemon."""

import io
import json
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import qrcode

from .config import CONFIG

security = HTTPBearer(auto_error=False)


class AuthManager:
    def __init__(self):
        self._token = self._load_or_generate_token()

    def _load_or_generate_token(self) -> str:
        if CONFIG.token_file.exists():
            token = CONFIG.token_file.read_text().strip()
            if len(token) >= 32:
                return token

        token = secrets.token_hex(24)
        CONFIG.token_file.write_text(token)
        CONFIG.token_file.chmod(0o600)
        return token

    @property
    def token(self) -> str:
        return self._token

    def verify_token(self, token: str) -> bool:
        if not token:
            return False
        return secrets.compare_digest(self._token, token.strip())

    def get_pairing_payload(self) -> dict:
        return {
            "version": CONFIG.version,
            "host": CONFIG.local_ip,
            "port": CONFIG.port,
            "token": self._token,
            "type": "antigravity-lan",
        }

    def get_pairing_json_string(self) -> str:
        return json.dumps(self.get_pairing_payload(), separators=(",", ":"))

    def render_ascii_qr(self) -> str:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=2,
        )
        qr.add_data(self.get_pairing_json_string())
        qr.make(fit=True)

        f = io.StringIO()
        qr.print_ascii(out=f, invert=True)
        return f.getvalue()

    def render_png_bytes(self) -> bytes:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(self.get_pairing_json_string())
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


AUTH = AuthManager()


async def verify_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> str:
    """FastAPI dependency verifying Bearer token authorization."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Bearer header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not AUTH.verify_token(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Antigravity authentication token",
        )
    return credentials.credentials
