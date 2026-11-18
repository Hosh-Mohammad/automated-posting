"""Orchestrates posting to every platform concurrently, isolating failures."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Optional, Sequence

import httpx

from app.config import Settings
from app.platforms.base import Platform, PlatformError
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.devto import DevToPlatform
from app.platforms.discord import DiscordPlatform
from app.platforms.github_gist import GithubGistPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.telegram import TelegramPlatform
from app.platforms.telegraph import TelegraphPlatform
from app.schemas import PlatformResult
from app.validation import extract_cta_link

logger = logging.getLogger(__name__)


def build_platforms(settings: Settings) -> list[Platform]:
    """All supported platforms. Selection is internal: the API caller never chooses."""
    return [
        BlueskyPlatform(settings),
        MastodonPlatform(settings),
        DiscordPlatform(settings),
        DevToPlatform(settings),
        GithubGistPlatform(settings),
        TelegraphPlatform(settings),
        TelegramPlatform(settings),
    ]


class PostingService:
    def __init__(
        self,
        platforms: Sequence[Platform],
        request_timeout: float = 20.0,
        platform_deadline: float = 45.0,
        client_factory: Optional[Callable[[], httpx.AsyncClient]] = None,
    ):
        self.platforms = list(platforms)
        self.request_timeout = request_timeout
        self.platform_deadline = platform_deadline
        self._client_factory = client_factory or self._default_client

    def _default_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.request_timeout,
            headers={"User-Agent": "automated-posting/1.0"},
        )

    async def publish(self, message: str) -> list[PlatformResult]:
        link = extract_cta_link(message)
        async with self._client_factory() as client:
            # Each task catches its own errors, so one failure never stops the rest.
            return list(
                await asyncio.gather(
                    *(self._run_one(p, client, message, link) for p in self.platforms)
                )
            )

    async def _run_one(
        self, platform: Platform, client: httpx.AsyncClient, message: str, link: str
    ) -> PlatformResult:
        missing = platform.missing_config()
        if missing:
            return self._failed(
                platform, f"Missing credentials: {', '.join(missing)}"
            )

        try:
            outcome = await asyncio.wait_for(
                platform.post(client, message, link), timeout=self.platform_deadline
            )
        except PlatformError as exc:
            return self._failed(platform, str(exc))
        except asyncio.TimeoutError:
            return self._failed(
                platform, f"Timed out after {self.platform_deadline:g}s"
            )
        except httpx.HTTPError as exc:
            # Only the exception type: messages/URLs may embed secrets (bot tokens).
            return self._failed(platform, f"Network error: {type(exc).__name__}")
        except Exception as exc:  # noqa: BLE001 - one platform must never break the rest
            logger.exception("Unexpected error posting to %s", platform.name)
            return self._failed(platform, f"Unexpected error: {type(exc).__name__}")

        now = datetime.now(timezone.utc)
        return PlatformResult(
            platform=platform.name,
            status="success",
            posted_url=outcome.url,
            public_access=outcome.public_access,
            date=now.date().isoformat(),
            time=now.strftime("%H:%M:%S"),
            error=None,
        )

    @staticmethod
    def _failed(platform: Platform, error: str) -> PlatformResult:
        return PlatformResult(
            platform=platform.name,
            status="failed",
            posted_url=None,
            public_access=False,
            date=None,
            time=None,
            error=error,
        )
