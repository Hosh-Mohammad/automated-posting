"""Telegraph (telegra.ph) - https://telegra.ph/api

Works out of the box: if TELEGRAPH_ACCESS_TOKEN is not set, an anonymous
account is created on first use and reused for the life of the process.
"""

from typing import Optional

import httpx

from app.platforms.base import Platform, PlatformError, PostOutcome, make_title, url_is_public

API = "https://api.telegra.ph"


class TelegraphPlatform(Platform):
    name = "Telegraph"

    def __init__(self, settings):
        super().__init__(settings)
        self._token: Optional[str] = settings.telegraph_access_token or None

    @staticmethod
    def _result(response: httpx.Response) -> dict:
        try:
            data = response.json()
        except ValueError:
            raise PlatformError(
                f"Unexpected response (HTTP {response.status_code})"
            ) from None
        if not data.get("ok"):
            error = str(data.get("error", "unknown error"))
            if "TOKEN" in error.upper():
                raise PlatformError(f"Authentication failed: {error}")
            raise PlatformError(f"Telegraph API error: {error}")
        return data["result"]

    async def _ensure_token(self, client: httpx.AsyncClient) -> str:
        if self._token:
            return self._token
        response = await client.post(
            f"{API}/createAccount",
            json={"short_name": "autoposter", "author_name": "Automated Posting"},
        )
        self._token = self._result(response)["access_token"]
        return self._token

    async def post(self, client, message, link) -> PostOutcome:
        token = await self._ensure_token(client)

        before, _, after = message.partition(link)
        nodes: list = []
        if before.strip():
            nodes.append(before)
        nodes.append({"tag": "a", "attrs": {"href": link}, "children": [link]})
        if after.strip():
            nodes.append(after)

        response = await client.post(
            f"{API}/createPage",
            json={
                "access_token": token,
                "title": make_title(message, link),
                "author_name": "Automated Posting",
                "content": [{"tag": "p", "children": nodes}],
            },
        )
        url = self._result(response)["url"]
        return PostOutcome(url=url, public_access=await url_is_public(client, url))
