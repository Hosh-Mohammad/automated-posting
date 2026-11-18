from app.platforms.base import (
    Platform, PostOutcome, api_error, describe_error, make_title, missing_vars,
)


class GithubGistPlatform(Platform):
    name = "GitHub Gist"

    def missing_config(self):
        return missing_vars([("GITHUB_TOKEN", self.settings.github_token)])

    async def post(self, client, message, link) -> PostOutcome:
        response = await client.post(
            "https://api.github.com/gists",
            headers={
                "Authorization": f"Bearer {self.settings.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "description": make_title(message, link),
                "public": True,
                "files": {"post.md": {"content": message}},
            },
        )
        if response.status_code != 201:
            raise api_error(response.status_code, describe_error(response))

        data = response.json()
        return PostOutcome(url=data.get("html_url"), public_access=bool(data.get("public")))