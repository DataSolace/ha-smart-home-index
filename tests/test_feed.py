"""The catalog feed: ETag revalidation, 304 handling and the offline fallback, with a fake HTTP layer."""

import asyncio
import json

import pytest

GOOD = {"version": 1, "count": 1, "devices": [{"id": "a", "name": "Widget (W-1000)", "modelTokens": ["W-1000"]}]}
URL = "https://example.test/api/catalog-lite"


class FakeHttp:
    """Answers with a scripted list of (status, headers, body) or raises the scripted exception."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def __call__(self, url, headers):
        self.calls.append((url, headers))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        status, hdrs, body = r
        return status, hdrs, json.dumps(body).encode() if not isinstance(body, bytes) else body


def run(coro):
    return asyncio.run(coro)


def test_first_download_keeps_the_etag_and_the_devices(feed):
    http = FakeHttp((200, {"ETag": '"abc"', "Content-Type": "application/json"}, GOOD))
    cat = run(feed.refresh(http, URL, None, "2026-10-10T12:00:00+00:00"))
    assert cat.source == "network" and cat.etag == '"abc"' and cat.fetched_at == "2026-10-10T12:00:00+00:00"
    assert cat.devices[0]["id"] == "a"
    assert "If-None-Match" not in http.calls[0][1]


def test_second_poll_sends_if_none_match_and_keeps_the_copy_on_304(feed):
    http = FakeHttp((200, {"etag": '"abc"'}, GOOD), (304, {}, b""))
    first = run(feed.refresh(http, URL, None, "t1"))
    second = run(feed.refresh(http, URL, first, "t2"))
    assert http.calls[1][1]["If-None-Match"] == '"abc"'
    assert second.source == "not_modified"
    assert second.devices == first.devices and second.etag == '"abc"'
    assert second.fetched_at == "t1" and second.checked_at == "t2"


def test_a_changed_catalog_replaces_the_copy(feed):
    changed = {"devices": [{"id": "a", "name": "Widget"}, {"id": "b", "name": "Gadget"}]}
    http = FakeHttp((200, {"ETag": '"v1"'}, GOOD), (200, {"ETag": '"v2"'}, changed))
    first = run(feed.refresh(http, URL, None, "t1"))
    second = run(feed.refresh(http, URL, first, "t2"))
    assert second.etag == '"v2"' and len(second.devices) == 2 and second.fetched_at == "t2"


def test_offline_keeps_working_from_the_cached_copy(feed):
    http = FakeHttp((200, {"ETag": '"abc"'}, GOOD), ConnectionError("no route"))
    first = run(feed.refresh(http, URL, None, "t1"))
    offline = run(feed.refresh(http, URL, first, "t2"))
    assert offline.source == "cache" and offline.devices == first.devices and offline.checked_at == "t1"


def test_a_server_error_or_junk_body_also_falls_back_to_the_cache(feed):
    http = FakeHttp((200, {"ETag": '"abc"'}, GOOD), (503, {}, b"down"), (200, {}, b"<html>cloudflare</html>"),
                    (200, {}, {"devices": []}))
    cat = run(feed.refresh(http, URL, None, "t1"))
    for _ in range(3):
        cat = run(feed.refresh(http, URL, cat, "t2"))
        assert cat.source == "cache" and cat.devices == GOOD["devices"]


def test_the_first_run_needs_the_network(feed):
    with pytest.raises(feed.FeedError):
        run(feed.refresh(FakeHttp(ConnectionError("offline")), URL, None, "t1"))
    with pytest.raises(feed.FeedError):
        run(feed.refresh(FakeHttp((500, {}, b"")), URL, None, "t1"))
    with pytest.raises(feed.FeedError):
        run(feed.refresh(FakeHttp((200, {}, {"devices": [{"name": "no id"}]})), URL, None, "t1"))


def test_a_cached_copy_survives_a_round_trip_through_storage(feed):
    http = FakeHttp((200, {"ETag": '"abc"'}, GOOD))
    cat = run(feed.refresh(http, URL, None, "t1"))
    back = feed.Catalog.from_stored(json.loads(json.dumps(cat.as_stored())))
    assert back.devices == cat.devices and back.etag == '"abc"' and back.source == "cache"
    assert feed.Catalog.from_stored(None) is None
    assert feed.Catalog.from_stored({"devices": []}) is None
