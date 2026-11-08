# Security Policy

## Supported Versions

Only the latest release and the current `main` branch receive security patches and updates.

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |
| < 1.0   | No        |

---

## Security Model & Threat Boundaries

Antigravity Mobile Daemon is designed with a zero-knowledge edge security architecture:

### 1. Private Network Isolation

- The gateway daemon listens on local network interfaces (`0.0.0.0:8767`) intended strictly for private home or office LAN communication.
- It does **not** expose any open relays, UPnP port forwards, or public tunnels to the internet.
- All client connections (REST and WebSockets) require authentication via cryptographically generated Bearer tokens (HMAC-SHA256).

### 2. Token Generation & Storage

- Authentication tokens are generated using Python's `secrets.token_urlsafe(32)` cryptographic generator.
- Tokens are stored in the user's private configuration directory (`~/.config/antigravity-mobile/token.txt`) with restricted POSIX file permissions (`0600`).
- Tokens are never logged to public files or transmitted unencrypted outside the local network.

### 3. File System & Path Traversal Protection

- Endpoints serving task logs (`/api/v1/sessions/{id}/tasks/{task_id}/log`) and artifacts (`/api/v1/sessions/{id}/artifacts/{name}`) sanitize all user-supplied identifiers using `pathlib.Path(name).name`.
- Direct traversal attacks (`../`, `/etc/passwd`) are structurally prevented by design.

---

## Reporting a Vulnerability

If you discover a security vulnerability or privacy concern:

1. **Do NOT open a public GitHub issue.**
2. Send an email to the maintainer: `vladimirfedorko225@gmail.com` with the subject `[SECURITY] Antigravity Mobile Daemon`.
3. Include detailed steps to reproduce the vulnerability, along with system logs and environment details.
4. Maintainers will review the report within 48 hours and coordinate a coordinated disclosure and patch release.
