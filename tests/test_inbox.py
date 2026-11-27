import json
from collections.abc import Callable, Sequence
from pathlib import Path

import cv2
import httpx2
import pytest
from fakes import BLACK_FRAME, FRAME_HEIGHT, FRAME_WIDTH, FakeInbox, ScriptedWindow

from innersight.cards import Box, CardColor, CardFace
from innersight.collection import (
    SAVE_KEY,
    SKIP_KEY,
    Candidate,
    CollectResult,
    CollectSession,
    accept_suggestions,
)
from innersight.dataset import TRAIN_SPLIT, VALIDATION_SPLIT, CardDataset
from innersight.errors import DatasetWriteError, InboxError
from innersight.inbox import (
    HttpInbox,
    InboxExample,
    PullReport,
    open_inbox,
    pull_examples,
)
from innersight.live_view import QUIT_KEY

CONTRACT_FILE = Path(__file__).parent.parent / "server" / "contract" / "example.json"
PNG = cv2.imencode(".png", BLACK_FRAME)[1].tobytes()
BOX = Box(10, 5, 30, 40)
FIRST_ID = "20261127T205301000000-0123abcd"
SECOND_ID = "20261127T205302000000-0123abcd"
THIRD_ID = "20261127T205303000000-0123abcd"
PULL_TOKEN = "p" * 32


def make_example(example_id: str = FIRST_ID, rank: str = "9", box: Box = BOX) -> InboxExample:
    return InboxExample(
        example_id, rank, "red", read_rank="6", read_color="red", confidence=0.6, box=box
    )


def review_with(*keys: int) -> Callable[[Sequence[Candidate]], CollectResult]:
    return CollectSession(ScriptedWindow(*keys)).run


def pull(inbox: FakeInbox, dataset_dir: Path, review: Callable = accept_suggestions) -> PullReport:
    return pull_examples(inbox, CardDataset(dataset_dir), review, limit=50)


def saved_names(dataset_dir: Path) -> list[str]:
    dataset = CardDataset(dataset_dir)
    return [
        name for split in (TRAIN_SPLIT, VALIDATION_SPLIT) for name in dataset.example_names(split)
    ]


def test_writes_a_pulled_example_into_the_dataset_with_its_true_rank(tmp_path: Path) -> None:
    pull(FakeInbox([make_example()], PNG), tmp_path)

    name = f"red_9_inbox_{FIRST_ID}"
    split = next(
        split
        for split in (TRAIN_SPLIT, VALIDATION_SPLIT)
        if CardDataset(tmp_path).has_example(split, name)
    )
    _, cards = CardDataset(tmp_path).read_example(split, name)
    assert [(card.rank, card.box) for card in cards] == [("9", BOX)]


def test_removes_an_example_from_the_inbox_once_it_is_saved(tmp_path: Path) -> None:
    inbox = FakeInbox([make_example()], PNG)

    report = pull(inbox, tmp_path)

    assert inbox.ids == []
    assert report.saved_count == 1


def test_removes_a_discarded_example_from_the_inbox_without_saving_it(tmp_path: Path) -> None:
    inbox = FakeInbox([make_example()], PNG)

    report = pull(inbox, tmp_path, review_with(SKIP_KEY))

    assert inbox.ids == []
    assert saved_names(tmp_path) == []
    assert report.discarded_count == 1


def test_leaves_the_examples_that_were_not_decided_on_in_the_inbox(tmp_path: Path) -> None:
    inbox = FakeInbox(
        [make_example(FIRST_ID), make_example(SECOND_ID), make_example(THIRD_ID)], PNG
    )

    report = pull(inbox, tmp_path, review_with(SAVE_KEY, QUIT_KEY))

    assert inbox.ids == [SECOND_ID, THIRD_ID]
    assert report.undecided_count == 2


def test_starts_the_review_at_the_card_set_in_the_app(tmp_path: Path) -> None:
    suggested: list[CardFace] = []

    def review(candidates: Sequence[Candidate]) -> CollectResult:
        suggested.extend(candidate.suggested for candidate in candidates)
        return CollectResult(saved=[], skipped=[])

    pull(FakeInbox([make_example(rank="9")], PNG), tmp_path, review)

    assert suggested == [CardFace(CardColor.RED, "9")]


def test_shows_in_the_review_what_the_detector_read(tmp_path: Path) -> None:
    read: list[str] = []

    def review(candidates: Sequence[Candidate]) -> CollectResult:
        read.extend(candidate.card.label for candidate in candidates)
        return CollectResult(saved=[], skipped=[])

    pull(FakeInbox([make_example()], PNG), tmp_path, review)

    assert read == ["red 6"]


@pytest.mark.parametrize(
    "example",
    [
        make_example(rank="joker"),
        make_example(box=Box(0, 0, FRAME_WIDTH + 1, FRAME_HEIGHT)),
        InboxExample(FIRST_ID, "9", "purple", "6", "red", 0.6, BOX),
    ],
)
def test_leaves_an_example_it_cannot_use_in_the_inbox_and_reports_it(
    tmp_path: Path, example: InboxExample
) -> None:
    inbox = FakeInbox([example], PNG)

    report = pull(inbox, tmp_path)

    assert inbox.ids == [FIRST_ID]
    assert report.unusable_ids == [FIRST_ID]
    assert saved_names(tmp_path) == []


def test_leaves_an_example_whose_picture_cannot_be_read_in_the_inbox(tmp_path: Path) -> None:
    inbox = FakeInbox([make_example()], b"not a picture")

    report = pull(inbox, tmp_path)

    assert inbox.ids == [FIRST_ID]
    assert report.unusable_ids == [FIRST_ID]


def test_keeps_the_example_in_the_inbox_when_it_could_not_be_saved(tmp_path: Path) -> None:
    inbox = FakeInbox([make_example()], PNG)
    blocking_file = tmp_path / "dataset"
    blocking_file.write_text("a file where the dataset directory should be")

    with pytest.raises(DatasetWriteError):
        pull(inbox, blocking_file)

    assert inbox.ids == [FIRST_ID]


def test_fetches_no_more_examples_than_the_limit(tmp_path: Path) -> None:
    inbox = FakeInbox([make_example(FIRST_ID), make_example(SECOND_ID)], PNG)

    pull_examples(inbox, CardDataset(tmp_path), accept_suggestions, limit=1)

    assert inbox.ids == [SECOND_ID]


def listed(example_id: str) -> dict:
    """An example as the inbox lists it: the shared contract sample with an id."""
    return {
        **json.loads(CONTRACT_FILE.read_text()),
        "id": example_id,
        "created_at": "2026-11-27T20:53:01Z",
    }


def page(*example_ids: str, next_after: str | None = None) -> httpx2.Response:
    pagination = {"has_more": next_after is not None, "next_after": next_after}
    body = {
        "success": True,
        "data": [listed(example_id) for example_id in example_ids],
        "meta": {"pagination": pagination},
    }
    return httpx2.Response(200, json=body)


def http_inbox(handler: Callable[[httpx2.Request], httpx2.Response]) -> HttpInbox:
    client = httpx2.Client(
        base_url="https://inbox.example",
        headers={"Authorization": f"Bearer {PULL_TOKEN}"},
        transport=httpx2.MockTransport(handler),
    )
    return HttpInbox(client)


def test_reads_the_example_in_the_shared_contract_file() -> None:
    inbox = http_inbox(lambda request: page(FIRST_ID))

    examples = inbox.list_examples(limit=10)

    assert examples == [
        InboxExample(
            FIRST_ID,
            "9",
            "red",
            read_rank="6",
            read_color="red",
            confidence=0.62,
            box=Box(120, 200, 360, 560),
        )
    ]


def test_sends_the_pull_token_with_every_request() -> None:
    tokens: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        tokens.append(request.headers["Authorization"])
        return (
            page()
            if request.method == "GET" and request.url.path.endswith("examples")
            else httpx2.Response(204)
        )

    inbox = http_inbox(handler)
    inbox.list_examples(limit=10)
    inbox.delete(FIRST_ID)

    assert tokens == [f"Bearer {PULL_TOKEN}"] * 2


def test_goes_on_to_the_next_page_until_the_inbox_has_no_more() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if "after" not in request.url.params:
            return page(FIRST_ID, next_after=FIRST_ID)
        assert request.url.params["after"] == FIRST_ID
        return page(SECOND_ID)

    examples = http_inbox(handler).list_examples(limit=10)

    assert [example.id for example in examples] == [FIRST_ID, SECOND_ID]


def test_asks_for_the_picture_and_the_removal_of_an_example_by_its_id() -> None:
    requests: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(f"{request.method} {request.url.path}")
        return httpx2.Response(200, content=PNG)

    inbox = http_inbox(handler)
    picture = inbox.fetch_image(FIRST_ID)
    inbox.delete(FIRST_ID)

    assert picture == PNG
    assert requests == [
        f"GET /api/v1/examples/{FIRST_ID}/image",
        f"DELETE /api/v1/examples/{FIRST_ID}",
    ]


def test_tells_what_the_inbox_said_when_it_refuses() -> None:
    refusal = {
        "success": False,
        "error": {"code": "UNAUTHORIZED", "message": "The token is not valid"},
    }
    inbox = http_inbox(lambda request: httpx2.Response(401, json=refusal))

    with pytest.raises(InboxError, match="The token is not valid"):
        inbox.list_examples(limit=10)


def test_tells_the_status_when_the_answer_is_not_from_the_inbox() -> None:
    inbox = http_inbox(lambda request: httpx2.Response(502, text="Bad Gateway"))

    with pytest.raises(InboxError, match="502"):
        inbox.list_examples(limit=10)


def test_tells_when_the_inbox_was_not_reached() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("no route to host")

    with pytest.raises(InboxError, match="not reached"):
        http_inbox(handler).list_examples(limit=10)


def test_tells_when_the_answer_is_not_a_listing() -> None:
    inbox = http_inbox(lambda request: httpx2.Response(200, json={"unexpected": True}))

    with pytest.raises(InboxError, match="not understood"):
        inbox.list_examples(limit=10)


def test_refuses_a_server_address_that_is_not_https() -> None:
    with pytest.raises(InboxError, match="https"):
        open_inbox("http://inbox.example", PULL_TOKEN)


@pytest.mark.parametrize("address", ["https://inbox.example", "http://localhost:8000"])
def test_takes_an_https_address_and_one_on_this_computer(address: str) -> None:
    assert isinstance(open_inbox(address, PULL_TOKEN), HttpInbox)
