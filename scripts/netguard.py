"""netguard.py — SSRF protection for outbound HTTP requests.

User-supplied URLs (from GitHub issues/comments) and third-party redirect
targets are fetched by the pipeline. ``validate_public_url`` rejects anything
that is not a plain ``http``/``https`` URL resolving to a globally routable
address, blocking requests to loopback, private, link-local, or cloud-metadata
endpoints (e.g. ``169.254.169.254``).
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}


class UnsafeURLError(ValueError):
    """Raised when a URL is not safe to fetch (bad scheme or non-public host)."""


def _is_public_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    # is_global is False for private/loopback/link-local/unspecified ranges.
    return ip.is_global and not ip.is_reserved and not ip.is_multicast


def validate_public_url(url: str) -> None:
    """Raise :class:`UnsafeURLError` if *url* is not a public http(s) URL.

    The host is resolved and every returned address must be globally routable,
    which prevents DNS names that point at internal/metadata IPs.
    """
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"scheme not allowed: {scheme!r}")

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("missing host")

    port = parsed.port or (443 if scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"DNS resolution failed for {host!r}") from exc

    if not infos:
        raise UnsafeURLError(f"no addresses for host {host!r}")

    for info in infos:
        ip_str = info[4][0]
        if not _is_public_ip(ip_str):
            raise UnsafeURLError(f"host {host!r} resolves to non-public address {ip_str}")


def is_public_url(url: str) -> bool:
    """Boolean convenience wrapper around :func:`validate_public_url`."""
    try:
        validate_public_url(url)
        return True
    except UnsafeURLError:
        return False
