"""http_client.py — shared pooled HTTP with retry/backoff for outbound calls.

Provides connection-pooled httpx clients (async + sync) and retry helpers so the
discovery adapters reuse TCP/TLS connections and transparently retry transient
failures (network errors and 429/5xx) with exponential backoff + jitter, honoring
``Retry-After`` when present.

- Adapters run concurrently and share one ``AsyncClient`` per discovery run
  (created with :func:`make_async_client`, lifecycle managed by the caller).
- Lower-volume sync call sites use the lazily-created singleton from
  :func:`get_sync_client` via :func:`request_sync`.
"""
from __future__ import annotations

import asyncio
import random
import time
from typing import Optional

import httpx

# Transient HTTP statuses worth retrying (rate-limit + gateway/server hiccups).
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_DEFAULT_RETRIES = 3
_DEFAULT_BACKOFF = 0.5  # base seconds for exponential backoff
_MAX_BACKOFF = 8.0

_LIMITS = httpx.Limits(max_connections=20, max_keepalive_connections=10)
_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
_USER_AGENT = (
    "awesome-ml-epigenetics-bot/1.0 "
    "(+https://github.com/jiajiexiao/awesome-ml-epigenetics)"
)

_sync_client: Optional[httpx.Client] = None


def make_async_client() -> httpx.AsyncClient:
    """Create a new pooled ``AsyncClient``. Caller owns its lifecycle.

    Transport-level ``retries`` cover connection establishment; status/transport
    retries are handled by :func:`arequest`.
    """
    return httpx.AsyncClient(
        limits=_LIMITS,
        timeout=_TIMEOUT,
        headers={"User-Agent": _USER_AGENT},
        transport=httpx.AsyncHTTPTransport(retries=2),
    )


def get_sync_client() -> httpx.Client:
    """Return a lazily-created, process-wide pooled sync client."""
    global _sync_client
    if _sync_client is None or _sync_client.is_closed:
        _sync_client = httpx.Client(
            limits=_LIMITS,
            timeout=_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
            transport=httpx.HTTPTransport(retries=2),
        )
    return _sync_client


def _sleep_seconds(resp: Optional[httpx.Response], attempt: int, base: float) -> float:
    """Backoff delay for *attempt*, honoring ``Retry-After`` when available."""
    if resp is not None:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), _MAX_BACKOFF)
            except ValueError:
                pass
    return min(base * (2 ** attempt) + random.uniform(0, base), _MAX_BACKOFF)


async def arequest(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    retries: int = _DEFAULT_RETRIES,
    base_backoff: float = _DEFAULT_BACKOFF,
    **kwargs,
) -> httpx.Response:
    """Async request with retry on transient status codes and transport errors."""
    resp: Optional[httpx.Response] = None
    for attempt in range(retries + 1):
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code in _RETRY_STATUS and attempt < retries:
                await asyncio.sleep(_sleep_seconds(resp, attempt, base_backoff))
                continue
            return resp
        except (httpx.TransportError, httpx.TimeoutException):
            if attempt >= retries:
                raise
            await asyncio.sleep(_sleep_seconds(None, attempt, base_backoff))
    assert resp is not None  # loop always sets resp before exhausting retries
    return resp


def request_sync(
    method: str,
    url: str,
    *,
    client: Optional[httpx.Client] = None,
    retries: int = _DEFAULT_RETRIES,
    base_backoff: float = _DEFAULT_BACKOFF,
    **kwargs,
) -> httpx.Response:
    """Sync request with retry on transient status codes and transport errors."""
    client = client or get_sync_client()
    resp: Optional[httpx.Response] = None
    for attempt in range(retries + 1):
        try:
            resp = client.request(method, url, **kwargs)
            if resp.status_code in _RETRY_STATUS and attempt < retries:
                time.sleep(_sleep_seconds(resp, attempt, base_backoff))
                continue
            return resp
        except (httpx.TransportError, httpx.TimeoutException):
            if attempt >= retries:
                raise
            time.sleep(_sleep_seconds(None, attempt, base_backoff))
    assert resp is not None
    return resp
