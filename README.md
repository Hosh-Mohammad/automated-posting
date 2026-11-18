# Automated Posting API

FastAPI service that publishes one short message (max 200 chars, exactly one CTA link) to several third-party platforms through their official APIs. Platforms run concurrently and independently: one failure never blocks the others.

## Platforms

| Platform | API used | Credentials | Public permalink |
|---|---|---|---|
| Telegraph | [Telegraph API](https://telegra.ph/api) `createPage` | None (anonymous account auto-created) or `TELEGRAPH_ACCESS_TOKEN` | Yes (verified with a GET) |
| Bluesky | AT Protocol `createSession` + `createRecord` | Handle + app password | Yes (public by protocol) |
| Mastodon | `POST /api/v1/statuses` | Instance URL + token (`write:statuses`) | Yes if status visibility is `public` |
| Telegram | Bot API `sendMessage` | Bot token + public `@channel` (bot is admin) | Yes for public channels |
| Discord | Incoming webhook | Webhook URL | No (members only) |
| DEV Community | Forem API v1 `POST /api/articles` | API key | Yes if `published` |

Platform selection is internal: every registered platform is attempted. A platform without credentials is reported as `failed` with `Missing credentials: ...`, and the rest still post. Telegraph works with zero setup.

LLM platforms (ChatGPT, Claude, etc.) expose no API for publishing public content, so none are included.

## Setup

```bash
cd automated-posting
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in the credentials you have
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Docs: http://localhost:4000/docs

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
    {"platform": "Telegraph", "status": "success", "posted_url": "https://telegra.ph/...", "public_access": true, "date": "2026-11-16", "time": "13:10:00", "error": null},
    {"platform": "Discord", "status": "failed", "posted_url": null, "public_access": false, "date": null, "time": null, "error": "Missing credentials: DISCORD_WEBHOOK_URL"}
  ]
}
```

Date and time are UTC.

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

All HTTP is mocked (`httpx.MockTransport`); no credentials or network needed.

## Notes

- Error messages never include request URLs, so bot tokens and webhook secrets are not leaked in responses.
- Each platform has a per-request timeout (`REQUEST_TIMEOUT`) and an overall deadline (`PLATFORM_DEADLINE`).
- To add a platform: subclass `Platform` in `app/platforms/`, then register it in `build_platforms`.
