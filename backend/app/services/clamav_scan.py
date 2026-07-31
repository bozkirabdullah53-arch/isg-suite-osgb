"""Optional ClamAV INSTREAM scan (TCP clamd). Disabled when CLAMAV_HOST is unset."""
from __future__ import annotations

import socket
import struct
import time

from app.core.config import settings

_CHUNK = 64 * 1024


def is_clamav_configured() -> bool:
    return bool((settings.clamav_host or "").strip())


def clamav_status_label() -> str:
    """disabled | reachable | unreachable — host yoksa ağ yok; /health'te çağırma maliyeti düşük."""
    host = (settings.clamav_host or "").strip()
    if not host:
        return "disabled"
    port = int(settings.clamav_port or 3310)
    timeout = min(2.0, float(settings.clamav_timeout_sec or 30.0))
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(b"zPING\0")
            resp = b""
            deadline = time.monotonic() + timeout
            while b"PONG" not in resp.upper() and time.monotonic() < deadline and len(resp) < 64:
                part = sock.recv(64)
                if not part:
                    break
                resp += part
            if b"PONG" in resp.upper():
                return "reachable"
            return "unreachable"
    except OSError:
        return "unreachable"


def scan_bytes(content: bytes) -> tuple[bool, str]:
    """Return (clean, detail). clean=False → reject upload."""
    host = (settings.clamav_host or "").strip()
    if not host:
        return True, "skipped"
    port = int(settings.clamav_port or 3310)
    timeout = float(settings.clamav_timeout_sec or 30.0)
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(b"zINSTREAM\0")
            for i in range(0, len(content), _CHUNK):
                chunk = content[i : i + _CHUNK]
                sock.sendall(struct.pack(">I", len(chunk)) + chunk)
            sock.sendall(struct.pack(">I", 0))
            resp = b""
            while b"\n" not in resp and len(resp) < 8192:
                part = sock.recv(4096)
                if not part:
                    break
                resp += part
            text = resp.decode("utf-8", errors="replace").strip()
            upper = text.upper()
            if "FOUND" in upper:
                return False, text or "FOUND"
            if "OK" in upper:
                return True, text or "OK"
            return False, text or "unexpected_clamav_response"
    except OSError as exc:
        return False, f"clamav_unreachable:{exc}"
