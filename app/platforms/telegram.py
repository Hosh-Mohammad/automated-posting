"""Telegram Bot API - https://core.telegram.org/bots/api#sendmessage

The bot must be an administrator of the target channel. The post URL is
publicly viewable only when the channel has a public @username.
"""

from app.platforms.base import (
    Platform,
    PostOutcome,
    api_error,
    describe_error,
    missing_vars,
)


class TelegramPlatform(Platform):
    name = "Telegram"

    def missing_config(self):
        s = self.settings
        return missing_vars(
            [
                ("TELEGRAM_BOT_TOKEN", s.telegram_bot_token),
                ("TELEGRAM_CHANNEL", s.telegram_channel),
            ]
        )

    async def post(self, client, message, link) -> PostOutcome:
        s = self.settings
        # The bot token is part of the URL, so errors must never echo the URL.
        response = await client.post(
            f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
            json={"chat_id": s.telegram_channel, "text": message},
        )
        try:
            data = response.json()
        except ValueError:
            raise api_error(response.status_code, describe_error(response)) from None
        if not data.get("ok"):
            raise api_error(
                int(data.get("error_code", response.status_code)),
                data.get("description"),
            )

        result = data["result"]
        username = (result.get("chat") or {}).get("username")
        if username:
            return PostOutcome(
                url=f"https://t.me/{username}/{result['message_id']}", public_access=True
            )
        # Private channel/group: no public permalink exists.
        return PostOutcome(url=None, public_access=False)
