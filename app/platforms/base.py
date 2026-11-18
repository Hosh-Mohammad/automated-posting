"""Shared platform abstractions and helpers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

import httpx

from app.config import Settings


class PlatformError(Exception):
    """A platform-level failure with a safe, user-presentable message."""


@dataclass(frozen=True)
class PostOutcome:
    url: Optional[str]
    public_access: bool


class Platform(ABC):
    """One third-party publishing target."""

    name: str

    def __init__(self, settings: Settings):
        self.settings = settings

    def missing_config(self) -> list[str]:
        """Names of required environment variables that are not set."""
        return []

    @abstractmethod
    async def post(
        self, client: httpx.AsyncClient, message: str, link: str
    ) -> PostOutcome:
        """Publish `message` and return where it ended up.

        Raise PlatformError (or let httpx errors propagate) on failure.
        """


def missing_vars(pairs: Iterable[Tuple[str, Optional[str]]]) -> list[str]:
    return [name for name, value in pairs if not value]


def describe_error(response: httpx.Response) -> str:
    """Best-effort extraction of an error description from an API response."""
    try:
        data = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(data, dict):
        for key in ("description", "message", "error_description", "error", "errors"):
            value = data.get(key)
            if value:
                return str(value)
    return response.text[:300]


def api_error(status_code: int, detail: Optional[str]) -> PlatformError:
    detail = (detail or "no details").strip()[:300]
    if status_code in (401, 403):
        return PlatformError(f"Authentication failed (HTTP {status_code}): {detail}")
    return PlatformError(f"HTTP {status_code}: {detail}")


def make_title(message: str, link: str, max_len: int = 80) -> str:
    """Derive a short title from the message text (without the link)."""
    text = " ".join(message.replace(link, " ").split()).strip(" -–—:,;")
    if not text:
        return "New post"
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


async def url_is_public(client: httpx.AsyncClient, url: str) -> bool:
    """Check that an unauthenticated GET of the URL succeeds."""
    try:
        response = await client.get(url, follow_redirects=True)
    except httpx.HTTPError:
        return False
    return response.status_code < 400
