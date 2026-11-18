"""Bluesky (AT Protocol) - https://docs.bsky.app/docs/api/com-atproto-server-create-session

Flow: createSession (handle + app password) -> createRecord (app.bsky.feed.post).
The link is attached as a rich-text facet so it is clickable. Bluesky posts
are public by protocol.
"""

from datetime import datetime, timezone

from app.platforms.base import (
    Platform,
    PlatformError,
    PostOutcome,
    api_error,
    describe_error,
    missing_vars,
)


class BlueskyPlatform(Platform):
    name = "Bluesky"

    def missing_config(self):
        s = self.settings
        return missing_vars(
            [
                ("BLUESKY_IDENTIFIER", s.bluesky_identifier),
                ("BLUESKY_APP_PASSWORD", s.bluesky_app_password),
            ]
        )

    async def post(self, client, message, link) -> PostOutcome:
        s = self.settings
        base = s.bluesky_service_url.rstrip("/")

        response = await client.post(
            f"{base}/xrpc/com.atproto.server.createSession",
            json={"identifier": s.bluesky_identifier, "password": s.bluesky_app_password},
        )
        if response.status_code != 200:
            raise api_error(response.status_code, describe_error(response))
        session = response.json()

        record = {
            "$type": "app.bsky.feed.post",
            "text": message,
            "createdAt": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
        }
        index = message.find(link)
        if index >= 0:
            # Facet offsets are UTF-8 *byte* positions, not character positions.
            start = len(message[:index].encode("utf-8"))
            record["facets"] = [
                {
                    "index": {"byteStart": start, "byteEnd": start + len(link.encode("utf-8"))},
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}],
                }
            ]

        response = await client.post(
            f"{base}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            json={
                "repo": session["did"],
                "collection": "app.bsky.feed.post",
                "record": record,
            },
        )
        if response.status_code != 200:
            raise api_error(response.status_code, describe_error(response))

        rkey = response.json()["uri"].rsplit("/", 1)[-1]
        handle = session.get("handle") or s.bluesky_identifier
        return PostOutcome(
            url=f"https://bsky.app/profile/{handle}/post/{rkey}", public_access=True
        )
