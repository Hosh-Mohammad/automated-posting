"""Message validation: length limit and exactly one valid CTA link."""

import re
from urllib.parse import urlparse  # noqa: F401  (kept for callers that need it)

from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

MAX_MESSAGE_LENGTH = 200

# Anything that looks like a link: http(s)://... or a bare www.... token.
_URL_CANDIDATE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
# Punctuation that commonly trails a URL in prose but is not part of it.
_TRAILING_PUNCTUATION = ".,;:!?)]}'\""
# Public hostname: dotted labels ending in an alphabetic TLD.
_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    re.IGNORECASE,
)
_url_adapter = TypeAdapter(AnyHttpUrl)


def find_link_candidates(message: str) -> list[str]:
    """Return every link-like token in the message, trailing punctuation removed."""
    return [
        match.group(0).rstrip(_TRAILING_PUNCTUATION)
        for match in _URL_CANDIDATE.finditer(message)
    ]


def validate_message(message: str) -> str:
    """Validate the message and return its single CTA link.

    Raises ValueError with a human-readable message when invalid.
    """
    if not message or not message.strip():
        raise ValueError("Message must not be empty.")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError(
            f"Message must not exceed {MAX_MESSAGE_LENGTH} characters "
            f"(got {len(message)})."
        )

    links = find_link_candidates(message)
    if not links:
        raise ValueError("Message must contain exactly one CTA link (found none).")
    if len(links) > 1:
        raise ValueError(
            f"Message must contain exactly one CTA link (found {len(links)})."
        )

    link = links[0]
    if link.lower().startswith("www."):
        raise ValueError("The CTA link must start with http:// or https://.")

    try:
        parsed = _url_adapter.validate_python(link)
    except ValidationError:
        raise ValueError(f"Invalid URL: {link}") from None
    if not parsed.host or not _HOSTNAME.match(parsed.host):
        raise ValueError(f"Invalid URL (host is not a valid domain): {link}")

    return link


def extract_cta_link(message: str) -> str:
    """Return the CTA link of an already-validated message."""
    return validate_message(message)
