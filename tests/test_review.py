from pathlib import Path

import pytest
from fakes import ScriptedWindow, record_bursts

from innersight.capture import ALL_BURSTS, Burst
from innersight.dataset import CardDataset
from innersight.live_view import QUIT_KEY
from innersight.review import (
    BACK_KEY,
    KEEP_KEY,
    RECAPTURE_KEY,
    SHEET_COLUMNS,
    TILE_WIDTH,
    ReviewSession,
)

FIRST, SECOND, THIRD = ALL_BURSTS[:3]
UNUSED_KEY = ord("x")


@pytest.fixture
def dataset(tmp_path: Path) -> CardDataset:
    record_bursts(tmp_path, [FIRST, SECOND, THIRD])
    return CardDataset(tmp_path)


def review(dataset: CardDataset, window: ScriptedWindow) -> list[Burst]:
    return ReviewSession(window, dataset).run([FIRST, SECOND, THIRD])


def test_returns_the_bursts_marked_for_recapture(dataset: CardDataset) -> None:
    rejected = review(dataset, ScriptedWindow(KEEP_KEY, RECAPTURE_KEY, KEEP_KEY))

    assert rejected == [SECOND]


def test_returns_nothing_when_every_burst_is_kept(dataset: CardDataset) -> None:
    rejected = review(dataset, ScriptedWindow(KEEP_KEY))

    assert rejected == []


def test_quit_key_ends_the_review_and_keeps_the_marks(dataset: CardDataset) -> None:
    rejected = review(dataset, ScriptedWindow(RECAPTURE_KEY, QUIT_KEY))

    assert rejected == [FIRST]


def test_keeping_a_burst_after_going_back_unmarks_it(dataset: CardDataset) -> None:
    rejected = review(dataset, ScriptedWindow(RECAPTURE_KEY, BACK_KEY, KEEP_KEY))

    assert rejected == []


def test_stays_on_the_same_burst_when_another_key_is_pressed(dataset: CardDataset) -> None:
    window = ScriptedWindow(UNUSED_KEY, KEEP_KEY)

    review(dataset, window)

    assert window.frames_shown == 4


def test_shows_the_frames_of_a_burst_side_by_side(dataset: CardDataset) -> None:
    window = ScriptedWindow(KEEP_KEY)

    review(dataset, window)

    assert window.last_frame is not None
    assert window.last_frame.shape[1] == SHEET_COLUMNS * TILE_WIDTH
