"""Tests: validation, failure isolation, and each platform integration.

No real network calls: platforms are exercised through httpx.MockTransport.
"""

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, get_posting_service
from app.platforms.base import Platform, PlatformError, PostOutcome
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.devto import DevToPlatform
from app.platforms.discord import DiscordPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.telegram import TelegramPlatform
from app.platforms.telegraph import TelegraphPlatform
from app.services.posting_service import PostingService, build_platforms

LINK = "https://example.com"
VALID = f"Check out our latest business platform and grow your online visibility. {LINK}"


def S(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


class StubPlatform(Platform):
    def __init__(self, name, outcome=None, error=None, missing=None, delay=0.0):
        self.name = name
        self._outcome, self._error = outcome, error
        self._missing, self._delay = missing or [], delay

    def missing_config(self):
        return self._missing

    async def post(self, client, message, link):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error:
            raise self._error
        return self._outcome


def ok_stub(name="OK"):
    return StubPlatform(name, outcome=PostOutcome("https://example.com/post/123", True))


# --------------------------------------------------------------------------
# API + validation
# --------------------------------------------------------------------------
@pytest.fixture
def client():
    stubs = [
        ok_stub("Platform A"),
        StubPlatform("Platform B", error=PlatformError("Authentication failed")),
    ]
    app.dependency_overrides[get_posting_service] = lambda: PostingService(stubs)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_partial_failure_response_shape(client):
    response = client.post("/posting", json={"message": VALID})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    a, b = body["results"]
    assert a["platform"] == "Platform A" and a["status"] == "success"
    assert a["posted_url"] == "https://example.com/post/123"
    assert a["public_access"] is True and a["error"] is None
    assert len(a["date"]) == 10 and len(a["time"]) == 8
    assert b == {
        "platform": "Platform B",
        "status": "failed",
        "posted_url": None,
        "public_access": False,
        "date": None,
        "time": None,
        "error": "Authentication failed",
    }


def test_success_false_when_every_platform_fails():
    stubs = [StubPlatform("X", error=PlatformError("down"))]
    app.dependency_overrides[get_posting_service] = lambda: PostingService(stubs)
    try:
        body = TestClient(app).post("/posting", json={"message": VALID}).json()
    finally:
        app.dependency_overrides.clear()
    assert body["success"] is False
    assert body["results"][0]["status"] == "failed"


@pytest.mark.parametrize(
    "message, fragment",
    [
        ("x" * 190 + f" {LINK}", "200 characters"),
        ("No link in this message", "exactly one CTA link (found none)"),
        (f"One {LINK} and two https://example.org", "found 2"),
        ("Visit www.example.com today", "http:// or https://"),
        ("Visit https://localhost now", "Invalid URL"),
        ("Visit https://exa mple.com now", "Invalid URL"),
        ("   ", "must not be empty"),
    ],
)
def test_invalid_messages_rejected(client, message, fragment):
    response = client.post("/posting", json={"message": message})
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["errors"][0]["field"] == "message"
    assert fragment in body["errors"][0]["message"]


@pytest.mark.parametrize("payload", [{}, {"message": 123}, {"message": None}])
def test_missing_or_wrong_type_rejected(client, payload):
    response = client.post("/posting", json=payload)
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "message"


def test_exactly_200_chars_is_accepted(client):
    message = "a" * (200 - len(LINK) - 1) + " " + LINK
    assert len(message) == 200
    assert client.post("/posting", json={"message": message}).status_code == 200


def test_trailing_punctuation_after_link_is_accepted(client):
    response = client.post("/posting", json={"message": "Read more: https://example.com/page."})
    assert response.status_code == 200


# --------------------------------------------------------------------------
# Service: failure isolation
# --------------------------------------------------------------------------
def test_one_failure_does_not_stop_others_and_order_is_kept():
    service = PostingService(
        [
            StubPlatform("Boom", error=RuntimeError("kaboom")),
            ok_stub("Fine"),
            StubPlatform("Api", error=PlatformError("HTTP 500: down")),
        ]
    )
    results = asyncio.run(service.publish(VALID))
    assert [r.platform for r in results] == ["Boom", "Fine", "Api"]
    assert [r.status for r in results] == ["failed", "success", "failed"]
    assert results[0].error == "Unexpected error: RuntimeError"
    assert results[2].error == "HTTP 500: down"


def test_missing_credentials_reported_per_platform():
    service = PostingService([StubPlatform("NoCreds", missing=["TOKEN_A", "TOKEN_B"]), ok_stub()])
    results = asyncio.run(service.publish(VALID))
    assert results[0].status == "failed"
    assert results[0].error == "Missing credentials: TOKEN_A, TOKEN_B"
    assert results[1].status == "success"


def test_platform_timeout_is_isolated():
    service = PostingService([StubPlatform("Slow", delay=1, outcome=PostOutcome("u", True)), ok_stub()],
                             platform_deadline=0.05)
    results = asyncio.run(service.publish(VALID))
    assert results[0].status == "failed" and "Timed out" in results[0].error
    assert results[1].status == "success"


def test_network_errors_do_not_leak_urls_or_secrets():
    err = httpx.ConnectError("https://api.telegram.org/bot123:SECRET/sendMessage")
    results = asyncio.run(PostingService([StubPlatform("Net", error=err)]).publish(VALID))
    assert results[0].error == "Network error: ConnectError"
    assert "SECRET" not in results[0].error


def test_at_least_five_platforms_registered():
    platforms = build_platforms(S())
    assert len(platforms) >= 5
    assert len({p.name for p in platforms}) == len(platforms)


def test_unconfigured_platforms_report_missing_vars():
    by_name = {p.name: p.missing_config() for p in build_platforms(S())}
    assert by_name["Telegraph"] == []  # auto-creates an anonymous account
    assert by_name["Bluesky"] == ["BLUESKY_IDENTIFIER", "BLUESKY_APP_PASSWORD"]
    assert by_name["Discord"] == ["DISCORD_WEBHOOK_URL"]


# --------------------------------------------------------------------------
# Platform integrations (mocked HTTP)
# --------------------------------------------------------------------------
def run_post(platform, handler, message=VALID, link=LINK):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await platform.post(http, message, link)

    return asyncio.run(go())


def test_telegraph_creates_account_then_page():
    def handler(request):
        if request.url.path == "/createAccount":
            return httpx.Response(200, json={"ok": True, "result": {"access_token": "tok"}})
        if request.url.path == "/createPage":
            body = json.loads(request.content)
            assert body["access_token"] == "tok"
            assert body["content"][0]["children"][-1]["attrs"]["href"] == LINK
            return httpx.Response(200, json={"ok": True, "result": {"url": "https://telegra.ph/Hello-11-16"}})
        return httpx.Response(200, text="<html></html>")  # public check

    outcome = run_post(TelegraphPlatform(S()), handler)
    assert outcome == PostOutcome("https://telegra.ph/Hello-11-16", True)


def test_telegraph_invalid_token_is_auth_failure():
    handler = lambda r: httpx.Response(200, json={"ok": False, "error": "ACCESS_TOKEN_INVALID"})
    with pytest.raises(PlatformError, match="Authentication failed"):
        run_post(TelegraphPlatform(S(telegraph_access_token="bad")), handler)


def test_bluesky_link_facet_uses_utf8_byte_offsets():
    message = "Héllo 🚀 world https://example.com/x"
    link = "https://example.com/x"
    expected_start = len("Héllo 🚀 world ".encode("utf-8"))
    seen = {}

    def handler(request):
        if request.url.path.endswith("createSession"):
            return httpx.Response(200, json={"accessJwt": "jwt", "did": "did:plc:abc", "handle": "me.bsky.social"})
        assert request.headers["authorization"] == "Bearer jwt"
        body = json.loads(request.content)
        seen["facet"] = body["record"]["facets"][0]
        assert body["repo"] == "did:plc:abc" and body["collection"] == "app.bsky.feed.post"
        return httpx.Response(200, json={"uri": "at://did:plc:abc/app.bsky.feed.post/3kxyz", "cid": "c"})

    platform = BlueskyPlatform(S(bluesky_identifier="me.bsky.social", bluesky_app_password="pw"))
    outcome = run_post(platform, handler, message=message, link=link)
    assert outcome == PostOutcome("https://bsky.app/profile/me.bsky.social/post/3kxyz", True)
    assert seen["facet"]["index"] == {"byteStart": expected_start, "byteEnd": expected_start + len(link)}


def test_bluesky_bad_credentials():
    handler = lambda r: httpx.Response(401, json={"error": "AuthenticationRequired", "message": "Invalid identifier or password"})
    platform = BlueskyPlatform(S(bluesky_identifier="x", bluesky_app_password="y"))
    with pytest.raises(PlatformError, match=r"Authentication failed \(HTTP 401\): Invalid identifier"):
        run_post(platform, handler)


def test_mastodon_posts_public_status():
    def handler(request):
        assert request.url.path == "/api/v1/statuses"
        assert request.headers["authorization"] == "Bearer tok"
        assert json.loads(request.content) == {"status": VALID, "visibility": "public"}
        return httpx.Response(200, json={"url": "https://mastodon.example/@me/1", "visibility": "public"})

    platform = MastodonPlatform(S(mastodon_instance_url="https://mastodon.example/", mastodon_access_token="tok"))
    assert run_post(platform, handler) == PostOutcome("https://mastodon.example/@me/1", True)


def test_telegram_public_channel_permalink_and_api_error():
    platform = TelegramPlatform(S(telegram_bot_token="123:abc", telegram_channel="@mychannel"))

    def good(request):
        assert request.url.path == "/bot123:abc/sendMessage"
        assert json.loads(request.content) == {"chat_id": "@mychannel", "text": VALID}
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42, "chat": {"username": "mychannel"}}})

    assert run_post(platform, good) == PostOutcome("https://t.me/mychannel/42", True)

    bad = lambda r: httpx.Response(400, json={"ok": False, "error_code": 400, "description": "Bad Request: chat not found"})
    with pytest.raises(PlatformError, match="HTTP 400: Bad Request: chat not found"):
        run_post(platform, bad)


def test_discord_webhook_is_not_public():
    webhook = "https://discord.com/api/webhooks/1/abc"

    def handler(request):
        if request.method == "POST":
            assert request.url.params["wait"] == "true"
            assert json.loads(request.content) == {"content": VALID}
            return httpx.Response(200, json={"id": "3", "channel_id": "2"})
        return httpx.Response(200, json={"guild_id": "1"})  # webhook lookup

    outcome = run_post(DiscordPlatform(S(discord_webhook_url=webhook)), handler)
    assert outcome == PostOutcome("https://discord.com/channels/1/2/3", False)


def test_devto_publishes_article():
    def handler(request):
        assert request.url.path == "/api/articles"
        assert request.headers["api-key"] == "key"
        article = json.loads(request.content)["article"]
        assert article["published"] is True and article["body_markdown"] == VALID
        assert LINK not in article["title"]
        return httpx.Response(201, json={"url": "https://dev.to/me/x-1", "published": True})

    assert run_post(DevToPlatform(S(devto_api_key="key")), handler) == PostOutcome("https://dev.to/me/x-1", True)


def test_devto_unauthorized():
    handler = lambda r: httpx.Response(401, json={"error": "unauthorized", "status": 401})
    with pytest.raises(PlatformError, match="Authentication failed"):
        run_post(DevToPlatform(S(devto_api_key="bad")), handler)
