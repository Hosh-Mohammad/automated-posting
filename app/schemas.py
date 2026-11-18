"""Pydantic request / response models."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.validation import MAX_MESSAGE_LENGTH, validate_message


class PostingRequest(BaseModel):
    message: str = Field(
        ...,
        description=(
            f"Message to publish: at most {MAX_MESSAGE_LENGTH} characters and "
            "exactly one http(s) CTA link."
        ),
        examples=[
            "Check out our latest business platform and grow your online "
            "visibility. https://example.com"
        ],
    )

    @field_validator("message")
    @classmethod
    def _check_message(cls, value: str) -> str:
        validate_message(value)
        return value


class PlatformResult(BaseModel):
    platform: str
    status: Literal["success", "failed"]
    posted_url: Optional[str] = None
    public_access: bool = False
    date: Optional[str] = Field(None, description="Posting date (UTC, YYYY-MM-DD)")
    time: Optional[str] = Field(None, description="Posting time (UTC, HH:MM:SS)")
    error: Optional[str] = None


class PostingResponse(BaseModel):
    success: bool = Field(
        ..., description="True when at least one platform published the message."
    )
    results: list[PlatformResult]


class FieldError(BaseModel):
    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    success: Literal[False] = False
    errors: list[FieldError]
