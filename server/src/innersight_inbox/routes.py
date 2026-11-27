"""The endpoints for examples: the app adds them, 'innersight pull' lists, reads and removes."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError

from innersight_inbox.auth import require_pull_token, require_upload_token
from innersight_inbox.errors import InvalidUpload
from innersight_inbox.png import read_png_size
from innersight_inbox.schemas import (
    ErrorResponse,
    ExampleListResponse,
    ExampleMetadata,
    ExampleResponse,
    ListMeta,
    Pagination,
)
from innersight_inbox.store import ID_PATTERN, ExampleStore

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/examples")

ExampleId = Annotated[str, Path(pattern=ID_PATTERN, description="The id the inbox gave")]
FAILURES = {
    400: {"model": ErrorResponse, "description": "The request is not as it should be"},
    401: {"model": ErrorResponse, "description": "The token is missing or not valid"},
    403: {"model": ErrorResponse, "description": "The token is for other work than this"},
}
NOT_FOUND = {404: {"model": ErrorResponse, "description": "There is no such example"}}


def get_store(request: Request) -> ExampleStore:
    return request.app.state.store


Store = Annotated[ExampleStore, Depends(get_store)]


@router.post(
    "",
    status_code=201,
    dependencies=[Depends(require_upload_token)],
    responses={**FAILURES, 507: {"model": ErrorResponse, "description": "The inbox is full"}},
)
def add_example(
    store: Store,
    image: Annotated[UploadFile, File(description="The whole camera frame, as a PNG picture")],
    metadata: Annotated[str, Form(description="An ExampleMetadata object, as JSON")],
) -> ExampleResponse:
    """Take in a frame from a game, with the true card that the player set for it."""
    try:
        told = ExampleMetadata.model_validate_json(metadata)
    except ValidationError as error:
        raise InvalidUpload(f"metadata: {describe_validation_errors(error.errors())}") from error
    content = image.file.read()
    if read_png_size(content) != (told.frame_width, told.frame_height):
        raise InvalidUpload("image: must be a PNG picture of the frame size in the metadata")
    example = store.add(content, told)
    logger.info("Stored example %s", example.id)
    return ExampleResponse(data=example)


@router.get("", dependencies=[Depends(require_pull_token)], responses=FAILURES)
def list_examples(
    store: Store,
    after: Annotated[
        str | None, Query(pattern=ID_PATTERN, description="List the examples after this id")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> ExampleListResponse:
    """List the examples in the order they were uploaded, a page at a time."""
    examples = store.list_examples(after, limit + 1)
    page = examples[:limit]
    has_more = len(examples) > limit
    pagination = Pagination(has_more=has_more, next_after=page[-1].id if has_more else None)
    return ExampleListResponse(data=page, meta=ListMeta(pagination=pagination))


@router.get(
    "/{example_id}/image",
    dependencies=[Depends(require_pull_token)],
    response_class=FileResponse,
    responses={**FAILURES, **NOT_FOUND},
)
def read_image(store: Store, example_id: ExampleId) -> FileResponse:
    """The picture of an example, as it was uploaded."""
    logger.info("Sent the picture of example %s", example_id)
    return FileResponse(store.image_path(example_id), media_type="image/png")


@router.delete(
    "/{example_id}",
    status_code=204,
    dependencies=[Depends(require_pull_token)],
    responses={**FAILURES, **NOT_FOUND},
)
def delete_example(store: Store, example_id: ExampleId) -> None:
    """Remove an example and its picture from the inbox."""
    store.delete(example_id)
    logger.info("Deleted example %s", example_id)


def describe_validation_errors(errors: list[dict]) -> str:
    """Every field that is wrong and what is wrong with it, in one line."""
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in errors
    )
