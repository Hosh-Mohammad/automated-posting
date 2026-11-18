"""FastAPI entry point.

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 4000
"""

import logging
from functools import lru_cache

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.schemas import PostingRequest, PostingResponse, ValidationErrorResponse
from app.services.posting_service import PostingService, build_platforms

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Automated Posting API",
    description=(
        "Publishes a short message with one CTA link to multiple third-party "
        "platforms. Platforms are handled independently: one failure never "
        "blocks the others."
    ),
    version="1.0.0",
)


@lru_cache
def get_posting_service() -> PostingService:
    settings = get_settings()
    return PostingService(
        build_platforms(settings),
        request_timeout=settings.request_timeout,
        platform_deadline=settings.platform_deadline,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for err in exc.errors():
        location = [str(part) for part in err.get("loc", ()) if part != "body"]
        message = str(err.get("msg", "Invalid input")).removeprefix("Value error, ")
        errors.append({"field": ".".join(location) or "body", "message": message})
    return JSONResponse(status_code=422, content={"success": False, "errors": errors})


@app.post(
    "/posting",
    response_model=PostingResponse,
    responses={422: {"model": ValidationErrorResponse}},
    summary="Publish a message to all configured platforms",
)
async def create_posting(
    payload: PostingRequest,
    service: PostingService = Depends(get_posting_service),
) -> PostingResponse:
    results = await service.publish(payload.message)
    return PostingResponse(
        success=any(r.status == "success" for r in results), results=results
    )
