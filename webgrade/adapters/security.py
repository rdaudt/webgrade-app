from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import socket
import ssl
from urllib.parse import urlparse

import httpx


SECURITY_HEADERS = {
    "strict_transport_security": "strict-transport-security",
    "content_security_policy": "content-security-policy",
    "x_frame_options": "x-frame-options",
    "x_content_type_options": "x-content-type-options",
    "referrer_policy": "referrer-policy",
}


def grade_security_headers(headers: httpx.Headers) -> dict[str, Any]:
    present = {
        logical_name: bool(headers.get(header_name))
        for logical_name, header_name in SECURITY_HEADERS.items()
    }
    count = sum(1 for value in present.values() if value)
    grade = {5: "A", 4: "B", 3: "C", 2: "D", 1: "E"}.get(count, "F")
    return {"grade": grade, "headers_present": present}


def run_security_headers(url: str, client: httpx.Client | None = None) -> dict[str, Any]:
    owns_client = client is None
    client = client or httpx.Client(timeout=20.0, follow_redirects=True)
    try:
        response = client.get(url)
        response.raise_for_status()
        summary = grade_security_headers(response.headers)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Security header inspection failed: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    return {
        "adapter_key": "security_headers",
        "viewport": "combined",
        "status": "ok",
        "summary": summary,
        "raw": {"headers": dict(response.headers)},
        "error": None,
    }


def inspect_tls_certificate(hostname: str, port: int = 443, timeout: float = 10.0) -> dict[str, Any]:
    context = ssl.create_default_context()
    with socket.create_connection((hostname, port), timeout=timeout) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as tls_socket:
            cert = tls_socket.getpeercert()

    not_after = cert.get("notAfter")
    if not not_after:
        return {"status": "invalid", "expires_at": None, "days_to_expiry": None}

    expires_at = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)
    days_to_expiry = (expires_at - datetime.now(tz=UTC)).days
    if days_to_expiry < 0:
        status = "expired"
    elif days_to_expiry <= 60:
        status = "expiring_soon"
    else:
        status = "valid"
    return {
        "status": status,
        "expires_at": expires_at.isoformat(),
        "days_to_expiry": days_to_expiry,
    }


def run_tls_certificate(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise RuntimeError("TLS inspection failed: URL hostname is missing")

    try:
        summary = inspect_tls_certificate(hostname)
        error = None
    except Exception as exc:  # noqa: BLE001
        summary = {"status": "invalid", "expires_at": None, "days_to_expiry": None}
        error = {"message": str(exc)}

    return {
        "adapter_key": "tls_certificate",
        "viewport": "combined",
        "status": "ok" if error is None else "partial",
        "summary": summary,
        "raw": summary,
        "error": error,
    }
