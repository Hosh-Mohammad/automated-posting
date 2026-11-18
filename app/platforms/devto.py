"""DEV Community (Forem API v1) - https://developers.forem.com/api/v1#tag/articles/operation/createArticle"""
from datetime import datetime, timezone
from app.platforms.base import (
    Platform,
    PostOutcome,
    api_error,
    describe_error,
    make_title,
    missing_vars,
)


class DevToPlatform(Platform):
    name = "DEV Community"

    def missing_config(self):
        return missing_vars([("DEVTO_API_KEY", self.settings.devto_api_key)])

    async def post(self, client, message, link) -> PostOutcome:
        response = await client.post(
            "https://dev.to/api/articles",
            headers={
                "api-key": self.settings.devto_api_key,
                "Accept": "application/vnd.forem.api-v1+json",
            },
            json={
                "article": {
                                        "title": f"{make_title(message, link)} ({datetime.now(timezone.utc):%H:%M:%S})",
                    "body_markdown": message,
                    "published": True,
                }
            },
        )
        if response.status_code not in (200, 201):
            raise api_error(response.status_code, describe_error(response))

        data = response.json()
        return PostOutcome(url=data.get("url"), public_access=bool(data.get("published")))
