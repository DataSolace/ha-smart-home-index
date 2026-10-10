"""Fetch the catalog-lite feed with ETag revalidation and an offline fallback. Pure Python, no HA imports.

The feed is https://smarthomeindex.com/api/catalog-lite. It answers 200 with a strong ETag, or 304 when
If-None-Match carries the ETag of the copy we already hold. The HTTP call itself is injected, so the
logic here is tested with a fake and Home Assistant supplies aiohttp at runtime.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any, Awaitable, Callable

# (url, request headers) -> (status, response headers, body bytes)
Fetch = Callable[[str, dict[str, str]], Awaitable[tuple[int, dict[str, str], bytes]]]

STORAGE_VERSION = 1


class FeedError(Exception):
    """The feed could not be read and there is no cached copy to fall back on."""


@dataclass(frozen=True)
class Catalog:
    devices: list[dict[str, Any]]
    etag: str | None = None
    fetched_at: str | None = None  # when the body was last downloaded
    checked_at: str | None = None  # when the feed last answered, 200 or 304
    source: str = "cache"  # network, not_modified, cache

    def as_stored(self) -> dict[str, Any]:
        return {"etag": self.etag, "fetched_at": self.fetched_at, "checked_at": self.checked_at,
                "devices": self.devices}

    @classmethod
    def from_stored(cls, data: dict[str, Any] | None) -> Catalog | None:
        if not data or not isinstance(data.get("devices"), list) or not data["devices"]:
            return None
        return cls(devices=data["devices"], etag=data.get("etag"), fetched_at=data.get("fetched_at"),
                   checked_at=data.get("checked_at"), source="cache")


def _header(headers: dict[str, str], name: str) -> str | None:
    name = name.lower()
    return next((v for k, v in headers.items() if k.lower() == name), None)


def parse_body(body: bytes) -> list[dict[str, Any]]:
    """Return the device list from a feed body, or raise FeedError if it is not a catalog."""
    try:
        data = json.loads(body)
    except ValueError as err:
        raise FeedError(f"feed is not JSON: {err}") from err
    devices = data.get("devices") if isinstance(data, dict) else None
    if not isinstance(devices, list) or not devices:
        raise FeedError("feed holds no devices")
    if not all(isinstance(d, dict) and d.get("id") and d.get("name") for d in devices):
        raise FeedError("feed devices lack id or name")
    return devices


async def refresh(fetch: Fetch, url: str, cached: Catalog | None, now: str) -> Catalog:
    """Fetch the feed, revalidating with the cached ETag. Fall back to the cached copy if the feed is unreachable."""
    headers = {"Accept": "application/json"}
    if cached and cached.etag:
        headers["If-None-Match"] = cached.etag

    def fallback(reason: str) -> Catalog:
        if cached and cached.devices:
            return replace(cached, source="cache")
        raise FeedError(reason)

    try:
        status, resp_headers, body = await fetch(url, headers)
    except Exception as err:  # noqa: BLE001 - any transport failure means "offline" here
        return fallback(f"could not reach {url}: {err}")

    if status == 304 and cached:
        return replace(cached, checked_at=now, source="not_modified")
    if status != 200:
        return fallback(f"{url} answered {status}")
    try:
        devices = parse_body(body)
    except FeedError as err:
        return fallback(str(err))
    return Catalog(devices=devices, etag=_header(resp_headers, "ETag"), fetched_at=now, checked_at=now,
                   source="network")
