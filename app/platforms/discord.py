"""Discord incoming webhook - https://discord.com/developers/docs/resources/webhook#execute-webhook

Messages are visible only to members of the server, so public_access is False.
"""

import httpx

from app.platforms.base import (
    Platform,
    PostOutcome,
    api_error,
    describe_error,
    missing_vars,
)


class DiscordPlatform(Platform):
    name = "Discord"

    def missing_config(self):
        return missing_vars([("DISCORD_WEBHOOK_URL", self.settings.discord_webhook_url)])

    async def post(self, client, message, link) -> PostOutcome:
        webhook = self.settings.discord_webhook_url
        # wait=true makes Discord return the created message instead of 204.
        response = await client.post(
            webhook, params={"wait": "true"}, json={"content": message}
        )
        if not 200 <= response.status_code < 300:
            raise api_error(response.status_code, describe_error(response))

        data = response.json()
        guild_id = data.get("guild_id") or await self._guild_id(client, webhook)
        if guild_id:
            url = f"https://discord.com/channels/{guild_id}/{data['channel_id']}/{data['id']}"
        else:
            url = None
        return PostOutcome(url=url, public_access=False)

    @staticmethod
    async def _guild_id(client: httpx.AsyncClient, webhook: str):
        """Webhook responses may omit guild_id; GET on the webhook has it."""
        try:
            response = await client.get(webhook)
            return response.json().get("guild_id") if response.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            return None
