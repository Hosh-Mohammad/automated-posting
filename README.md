# Automated Posting API

FastAPI service that publishes one short message (max 200 characters, exactly one CTA link) to several third-party platforms through their official APIs. Platforms run concurrently and independently: one failure never blocks the others.

## Platforms

| Platform | API used | Credentials (env vars) | Public permalink |
|---|---|---|---|
| Telegraph | [Telegraph API](https://telegra.ph/api) `createPage` | None (anonymous account auto-created), or `TELEGRAPH_ACCESS_TOKEN` | Yes (verified with a GET) |
| Bluesky | AT Protocol `createSession` + `createRecord` | `BLUESKY_IDENTIFIER`, `BLUESKY_APP_PASSWORD` | Yes (public by protocol) |
| Mastodon | `POST /api/v1/statuses` | `MASTODON_INSTANCE_URL`, `MASTODON_ACCESS_TOKEN` (`write:statuses`) | Yes if visibility is `public` |
| Telegram | Bot API `sendMessage` | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL` (bot is admin of a public channel) | Yes for public channels |
| Discord | Incoming webhook | `DISCORD_WEBHOOK_URL` | No (members only) |
| DEV Community | Forem API v1 `POST /api/articles` | `DEVTO_API_KEY` | Yes if `published` |
| GitHub Gist | REST `POST /gists` | `GITHUB_TOKEN` (`gist` scope) | Yes (public gist) |

Platform selection is internal: every registered platform is attempted. A platform without credentials is reported as `failed` with `Missing credentials: ...`, and the rest still post. Telegraph works without any credentials.

LLM platforms (ChatGPT, Claude, etc.) expose no API for publishing public content, so none are included.

## Setup

Requires Python 3.10 or newer.

**Windows (Command Prompt)**
```bat
cd automated-posting
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --host 0.0.0.0 --port 4000
```

**macOS / Linux**
```bash
cd automated-posting
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Fill in the credentials you have in `.env` (never commit this file), then restart the server after any change. Docs: http://localhost:4000/docs

## Usage

```bash
curl -X POST http://localhost:4000/posting \
  -H "Content-Type: application/json" \
  -d '{"message": "Check out our latest business platform and grow your online visibility. https://example.com"}'
```

Response (`success` is true when at least one platform published):

```json
{
  "success": true,
  "results": [
    {"platform": "GitHub Gist", "status": "success", "posted_url": "https://gist.github.com/<user>/<id>", "public_access": true, "date": "2026-11-18", "time": "13:35:12", "error": null},
    {"platform": "Telegram", "status": "failed", "posted_url": null, "public_access": false, "date": null, "time": null, "error": "Missing credentials: TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL"}
  ]
}
```

Date and time are UTC. Each platform returns its own result object.

### Sample output from a real run

{
  "success": true,
  "results": [
    {
      "platform": "Bluesky",
      "status": "success",
      "posted_url": "https://bsky.app/profile/hosh01.bsky.social/post/3n2lrhbglqx22",
      "public_access": true,
      "date": "2026-11-18",
      "time": "14:30:32",
      "error": null
    },
    {
      "platform": "Mastodon",
      "status": "success",
      "posted_url": "https://mastodon.social/@hosh01/117637921633726855",
      "public_access": true,
      "date": "2026-11-18",
      "time": "14:30:32",
      "error": null
    },
    {
      "platform": "Discord",
      "status": "success",
      "posted_url": "https://discord.com/channels/1572514489692201030/1572514490313089026/1572620022856294446",
      "public_access": false,
      "date": "2026-11-18",
      "time": "14:30:32",
      "error": null
    },
    {
      "platform": "DEV Community",
      "status": "success",
      "posted_url": "https://dev.to/hoshmohammad/check-out-our-latest-business-platform-and-grow-your-online-visibility-143030-437m",
      "public_access": false,
      "date": "2026-11-18",
      "time": "14:30:31",
      "error": null
    },
    {
      "platform": "GitHub Gist",
      "status": "success",
      "posted_url": "https://gist.github.com/Hosh-Mohammad/4f598c2e8056f3e2914913d32589e6a9",
      "public_access": true,
      "date": "2026-11-18",
      "time": "14:30:32",
      "error": null
    },
    {
      "platform": "Telegraph",
      "status": "failed",
      "posted_url": null,
      "public_access": false,
      "date": null,
      "time": null,
      "error": "Network error: ConnectTimeout"
    },
    {
      "platform": "Telegram",
      "status": "failed",
      "posted_url": null,
      "public_access": false,
      "date": null,
      "time": null,
      "error": "Missing credentials: TELEGRAM_BOT_TOKEN"
    }
  ]
}

## Validation (HTTP 422)

- Message must be non-empty and at most 200 characters.
- Exactly one link; it must be a valid `http(s)://` URL with a real domain (bare `www.` links and `localhost` are rejected).

```json
{"success": false, "errors": [{"field": "message", "message": "Message must contain exactly one CTA link (found 2)."}]}
```

## Tests

```bash
pytest
```

All HTTP is mocked (`httpx.MockTransport`); no credentials or network access are needed.

## Notes

- Error messages never include request URLs, so bot tokens and webhook secrets are not leaked in responses.
- Each platform has a per-request timeout (`REQUEST_TIMEOUT`, default 20 s) and an overall deadline (`PLATFORM_DEADLINE`, default 45 s).
- Some platforms may be unreachable from certain networks (for example Telegram or Telegraph in some countries). Such a platform simply reports `failed` and the others continue.
- DEV Community rejects an identical title posted within five minutes, so its article title includes the posting time.
- To add a platform: subclass `Platform` in `app/platforms/`, then register it in `build_platforms` in `app/services/posting_service.py`.