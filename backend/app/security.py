"""Security middleware and helpers (OWASP Top 10 2021 references in comments)."""
from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict, deque

from fastapi import HTTPException, Request
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

security_log = logging.getLogger("security")

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "pdm-demo"


class SecurityHeadersMiddleware:
    """Adds hardening headers to every response (A05 Security Misconfiguration)."""

    def __init__(self, app: ASGIApp, enable_hsts: bool) -> None:
        self.app = app
        self.headers = [
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"no-referrer"),
            (b"cache-control", b"no-store"),
            (b"cross-origin-opener-policy", b"same-origin"),
            (b"cross-origin-resource-policy", b"same-origin"),
            (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
            # The API only returns JSON, so nothing may load or frame it.
            (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
        ]
        if enable_hsts:
            self.headers.append((b"strict-transport-security", b"max-age=63072000; includeSubDomains"))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"server"]
                headers.extend(self.headers)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodySizeLimitMiddleware:
    """Rejects request bodies over a fixed size, including chunked uploads (A04 / DoS)."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for key, value in scope.get("headers", []):
            if key == b"content-length" and value.isdigit() and int(value) > self.max_bytes:
                await _reject_too_large(send)
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:  # chunked body with no Content-Length
                    security_log.warning("request_body_too_large")
                    raise StarletteHTTPException(status_code=413, detail="Request body too large")
            return message

        await self.app(scope, limited_receive, send)


async def _reject_too_large(send: Send) -> None:
    security_log.warning("request_body_too_large")
    await send({"type": "http.response.start", "status": 413,
                "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": b'{"detail":"Request body too large"}'})


class RateLimiter:
    """Sliding-window limiter per client and bucket (A04 Insecure Design: abuse and cost control).

    In-memory, so it is per process. Run one backend replica or replace this with a
    shared store (e.g. Redis) when scaling out.
    """

    def __init__(self, max_clients: int = 10_000) -> None:
        self._hits: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_clients = max_clients

    def check(self, client: str, bucket: str, limit: int, window_s: float = 60.0) -> bool:
        now = time.monotonic()
        key = (client, bucket)
        with self._lock:
            hits = self._hits.pop(key, deque())
            while hits and now - hits[0] > window_s:
                hits.popleft()
            allowed = len(hits) < limit
            if allowed:
                hits.append(now)
            self._hits[key] = hits
            while len(self._hits) > self._max_clients:  # bound memory under IP-spraying
                self._hits.popitem(last=False)
            return allowed


def client_ip(request: Request, trust_proxy: bool) -> str:
    """Client address. Proxy headers are trusted only when the operator says a proxy sets them."""
    if trust_proxy:
        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip[:64]
    return request.client.host if request.client else "unknown"


def require_csrf_header(request: Request) -> None:
    """State-changing requests must carry a custom header.

    Browsers cannot add custom headers cross-site without a CORS preflight, and CORS
    only allows our own origin, so forged cross-site POSTs fail (A01).
    """
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        security_log.warning("csrf_header_missing path=%s", request.url.path)
        raise HTTPException(status_code=403, detail="Forbidden")
