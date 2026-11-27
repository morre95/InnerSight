"""Fetch the examples collected in the app from the inbox on the user's server."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

import cv2
import httpx2
import numpy as np

from innersight.cards import RANKS, Box, Card, CardColor, CardFace, Detection
from innersight.collection import Candidate, CollectResult, save_collected
from innersight.dataset import CardDataset
from innersight.errors import InboxError

EXAMPLES_PATH = "/api/v1/examples"
PAGE_SIZE = 50
TIMEOUT_SECONDS = 30.0
KEY_PREFIX = "inbox_"
# A server on this computer is reached without HTTPS, for trying the inbox out.
LOCAL_HOSTS = ("localhost", "127.0.0.1")


@dataclass(frozen=True)
class InboxExample:
    """An example as the inbox lists it: the true card set in the app, and what was read."""

    id: str
    rank: str
    color: str
    read_rank: str
    read_color: str
    confidence: float
    box: Box


class Inbox(Protocol):
    def list_examples(self, limit: int) -> list[InboxExample]:
        """The oldest examples in the inbox, at most `limit` of them."""
        ...

    def fetch_image(self, example_id: str) -> bytes: ...

    def delete(self, example_id: str) -> None: ...


@dataclass(frozen=True)
class PullReport:
    """What became of the examples that were listed."""

    saved_count: int
    discarded_count: int
    undecided_count: int
    unusable_ids: list[str]


def pull_examples(
    inbox: Inbox,
    dataset: CardDataset,
    review: Callable[[Sequence[Candidate]], CollectResult],
    limit: int,
) -> PullReport:
    """Move examples from the inbox into the dataset, by way of the review.

    An example leaves the inbox once it is saved here or discarded in the review. One that the
    review did not reach, or that cannot be used, stays there.
    """
    ids_by_key: dict[str, str] = {}
    candidates: list[Candidate] = []
    unusable_ids: list[str] = []
    for example in inbox.list_examples(limit):
        candidate = _as_candidate(example, inbox.fetch_image(example.id))
        if candidate is None:
            unusable_ids.append(example.id)
        else:
            candidates.append(candidate)
            ids_by_key[candidate.key] = example.id

    result = review(candidates)
    if result.saved:
        save_collected(dataset, result.saved)
    for decided in (*result.saved, *result.skipped):
        inbox.delete(ids_by_key[decided.key])
    return PullReport(
        saved_count=len(result.saved),
        discarded_count=len(result.skipped),
        undecided_count=len(candidates) - len(result.saved) - len(result.skipped),
        unusable_ids=unusable_ids,
    )


def _as_candidate(example: InboxExample, image: bytes) -> Candidate | None:
    """The example as a candidate that starts at the card set in the app.

    None if it cannot be used: the picture cannot be read, the box is not inside it, or the
    card is one that this version does not know.
    """
    frame = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None or example.rank not in RANKS or not _is_inside(example.box, frame):
        return None
    try:
        suggested = CardFace(CardColor(example.color), example.rank)
        read_color = CardColor(example.read_color)
    except ValueError:
        return None
    detection = Detection(example.read_rank, example.confidence, example.box)
    return Candidate(f"{KEY_PREFIX}{example.id}", frame, Card(detection, read_color), suggested)


def _is_inside(box: Box, frame: np.ndarray) -> bool:
    frame_height, frame_width = frame.shape[:2]
    return 0 <= box.x1 < box.x2 <= frame_width and 0 <= box.y1 < box.y2 <= frame_height


class HttpInbox:
    """The inbox as reached over HTTP. The client holds its address and the pull token."""

    def __init__(self, client: httpx2.Client) -> None:
        self._client = client

    def list_examples(self, limit: int) -> list[InboxExample]:
        examples: list[InboxExample] = []
        after = None
        while len(examples) < limit:
            page, after = self._list_page(after, min(PAGE_SIZE, limit - len(examples)))
            examples += page
            if after is None:
                break
        return examples

    def _list_page(self, after: str | None, limit: int) -> tuple[list[InboxExample], str | None]:
        """One page of examples, and the id to go on after, or None when it was the last."""
        params: dict[str, str | int] = {"limit": limit}
        if after is not None:
            params["after"] = after
        response = self._request("GET", EXAMPLES_PATH, "list the examples", params=params)
        try:
            body = response.json()
            page = [_parse_example(item) for item in body["data"]]
            return page, body["meta"]["pagination"]["next_after"]
        except (KeyError, TypeError, ValueError) as error:
            raise InboxError(
                f"The inbox answered in a way that is not understood: {error!r}"
            ) from error

    def fetch_image(self, example_id: str) -> bytes:
        path = f"{EXAMPLES_PATH}/{example_id}/image"
        return self._request("GET", path, f"fetch the picture of {example_id}").content

    def delete(self, example_id: str) -> None:
        self._request("DELETE", f"{EXAMPLES_PATH}/{example_id}", f"remove {example_id}")

    def _request(self, method: str, path: str, task: str, **options: object) -> httpx2.Response:
        try:
            response = self._client.request(method, path, **options)
        except httpx2.HTTPError as error:
            raise InboxError(f"Could not {task}: the inbox was not reached ({error})") from error
        if response.is_error:
            raise InboxError(f"Could not {task}: {_describe_failure(response)}")
        return response


def open_inbox(server_url: str, token: str) -> HttpInbox:
    """Reach the inbox at the address with the pull token. The address must be an HTTPS one."""
    address = urlsplit(server_url)
    if address.scheme != "https" and address.hostname not in LOCAL_HOSTS:
        raise InboxError(f"The address of the inbox must start with https://, not {server_url}")
    client = httpx2.Client(
        base_url=server_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT_SECONDS,
    )
    return HttpInbox(client)


def _parse_example(item: dict) -> InboxExample:
    box = item["box"]
    return InboxExample(
        id=item["id"],
        rank=item["rank"],
        color=item["color"],
        read_rank=item["read_rank"],
        read_color=item["read_color"],
        confidence=float(item["confidence"]),
        box=Box(box["x1"], box["y1"], box["x2"], box["y2"]),
    )


def _describe_failure(response: httpx2.Response) -> str:
    """What the inbox said went wrong, or the status alone when the answer is not its own."""
    try:
        return response.json()["error"]["message"]
    except (KeyError, TypeError, ValueError):
        return f"the server answered {response.status_code} {response.reason_phrase}"
