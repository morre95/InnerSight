"""Put the inbox together: the endpoints, who may call them, and how a failure is answered."""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from innersight_inbox.errors import InboxError
from innersight_inbox.routes import describe_validation_errors, router
from innersight_inbox.schemas import ErrorBody, ErrorResponse
from innersight_inbox.settings import Settings
from innersight_inbox.store import ExampleStore

logger = logging.getLogger(__name__)


def create_app(settings: Settings) -> FastAPI:
    # The pages that describe the API are left out: the inbox has one user, who has the code.
    app = FastAPI(
        title="InnerSight inbox",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        max_body_size=settings.max_body_bytes,
    )
    app.state.settings = settings
    app.state.store = ExampleStore(settings.data_dir, settings.max_examples)
    # A browser may only upload. Pulling is done from the command line, which needs no CORS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_methods=["POST"],
        allow_headers=["Authorization"],
    )
    app.include_router(router, prefix="/api/v1")
    app.add_api_route("/healthz", _report_health, include_in_schema=False)
    app.add_exception_handler(InboxError, _answer_inbox_error)
    app.add_exception_handler(RequestValidationError, _answer_invalid_request)
    app.add_exception_handler(HTTPException, _answer_http_error)
    app.add_exception_handler(Exception, _answer_unexpected_error)
    return app


def create_app_from_environment() -> FastAPI:
    """What the server runs. It fails here, at the start, when a setting is missing."""
    return create_app(Settings())


def _report_health() -> dict[str, bool]:
    return {"success": True}


def _failure(status_code: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message))
    return JSONResponse(body.model_dump(), status_code=status_code)


def _answer_inbox_error(request: Request, error: InboxError) -> JSONResponse:
    return _failure(error.status_code, error.code, error.message)


def _answer_invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
    return _failure(400, "INVALID_REQUEST", describe_validation_errors(error.errors()))


def _answer_http_error(request: Request, error: HTTPException) -> JSONResponse:
    """A failure that the framework found itself, such as a path that does not exist."""
    status = HTTPStatus(error.status_code)
    return _failure(status.value, status.name, status.phrase)


def _answer_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    logger.error("%s %s failed", request.method, request.url.path, exc_info=error)
    return _failure(500, "INTERNAL_ERROR", "The inbox failed to handle the request")
