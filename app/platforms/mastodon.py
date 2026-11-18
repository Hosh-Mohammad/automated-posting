"""Mastodon - https://docs.joinmastodon.org/methods/statuses/#create

Needs an app access token with the `write:statuses` scope.
"""

from app.platforms.base import (
    Platform,
    PostOutcome,
    api_error,
    describe_error,
    missing_vars,
)


class MastodonPlatform(Platform):
    name = "Mastodon"

    def missing_config(self):
        s = self.settings
        return missing_vars(
            [
                ("MASTODON_INSTANCE_URL", s.mastodon_instance_url),
                ("MASTODON_ACCESS_TOKEN", s.mastodon_access_token),
            ]
        )

    async def post(self, client, message, link) -> PostOutcome:
        s = self.settings
        response = await client.post(
            f"{s.mastodon_instance_url.rstrip('/')}/api/v1/statuses",
            headers={"Authorization": f"Bearer {s.mastodon_access_token}"},
            json={"status": message, "visibility": "public"},
        )
        if response.status_code != 200:
            raise api_error(response.status_code, describe_error(response))

        data = response.json()
        return PostOutcome(
            url=data.get("url") or data.get("uri"),
            public_access=data.get("visibility") == "public",
        )
