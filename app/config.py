"""Application settings, loaded from environment variables (or a local .env file)."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Per-HTTP-request timeout (seconds) used for every platform call.
    request_timeout: float = 20.0
    # Hard deadline (seconds) for one platform's whole posting flow.
    platform_deadline: float = 45.0

    # Telegraph (telegra.ph) - token is optional; an anonymous account is
    # created automatically when it is not provided.
    telegraph_access_token: Optional[str] = None

    # Bluesky (AT Protocol) - use an *app password*, never the main password.
    bluesky_service_url: str = "https://bsky.social"
    bluesky_identifier: Optional[str] = None
    bluesky_app_password: Optional[str] = None

    # Mastodon - any instance, e.g. https://mastodon.social
    mastodon_instance_url: Optional[str] = None
    mastodon_access_token: Optional[str] = None

    # Telegram Bot API - bot must be an admin of the (public) channel.
    telegram_bot_token: Optional[str] = None
    telegram_channel: Optional[str] = None  # e.g. @my_public_channel

    # Discord incoming webhook
    discord_webhook_url: Optional[str] = None

    # DEV Community (Forem API)
    devto_api_key: Optional[str] = None
    github_token: Optional[str] = None

@lru_cache
def get_settings() -> Settings:
    return Settings()
