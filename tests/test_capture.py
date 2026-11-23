import itertools
import random
from pathlib import Path

import numpy as np
import pytest

from innersight.capture import (
    CAPTURE_STEPS,
    CARD_WIDTH_TO_HEIGHT,
    FRAMES_PER_POSITION,
    POSITIONS_PER_STEP,
    RECORD_KEY,
    SKIP_KEY,
    CaptureSession,
    choose_guide_box,
)
from innersight.cards import RANKS
from innersight.dataset import CardDataset
from innersight.live_view import QUIT_KEY

FRAME_HEIGHT = 48
FRAME_WIDTH = 64
FRAME = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
FRAMES_PER_STEP_IN_TRAIN = (POSITIONS_PER_STEP - 1) * FRAMES_PER_POSITION


class ScriptedWindow:
    """Stands in for the preview window: presses the scripted keys, then repeats the last one."""

    def __init__(self, *keys: int) -> None:
        self._keys = list(keys)
        self.frames_shown = 0

    def __call__(self, frame_bgr: np.ndarray) -> int:
        self.frames_shown += 1
        return self._keys.pop(0) if len(self._keys) > 1 else self._keys[0]


def run_session(dataset_dir: Path, window: ScriptedWindow) -> None:
    endless_frames = itertools.repeat(FRAME)
    CaptureSession(endless_frames, window, CardDataset(dataset_dir), random.Random(0)).run()


def image_names(dataset_dir: Path, split: str) -> list[str]:
    return sorted(image.name for image in (dataset_dir / split / "images").glob("*.jpg"))


@pytest.fixture(scope="module")
def fully_recorded_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    dataset_dir = tmp_path_factory.mktemp("dataset")
    run_session(dataset_dir, ScriptedWindow(RECORD_KEY))
    return dataset_dir


def test_records_every_step_into_the_train_split(fully_recorded_dir: Path) -> None:
    train_images = image_names(fully_recorded_dir, "train")

    assert len(train_images) == len(CAPTURE_STEPS) * FRAMES_PER_STEP_IN_TRAIN


def test_holds_back_one_position_of_every_step_for_validation(fully_recorded_dir: Path) -> None:
    validation_images = image_names(fully_recorded_dir, "valid")

    assert len(validation_images) == len(CAPTURE_STEPS) * FRAMES_PER_POSITION


def test_labels_a_card_frame_with_the_rank_of_the_card(fully_recorded_dir: Path) -> None:
    label = (fully_recorded_dir / "train" / "labels" / "red_7_p0_f0.txt").read_text()

    class_id = int(label.split()[0])
    assert RANKS[class_id] == "7"


def test_labels_background_frames_with_no_card(fully_recorded_dir: Path) -> None:
    label = (fully_recorded_dir / "train" / "labels" / "background_p0_f0.txt").read_text()

    assert label == ""


def test_asks_nothing_when_every_step_is_already_recorded(fully_recorded_dir: Path) -> None:
    window = ScriptedWindow(RECORD_KEY)

    run_session(fully_recorded_dir, window)

    assert window.frames_shown == 0


def test_quit_key_stops_before_anything_is_recorded(tmp_path: Path) -> None:
    run_session(tmp_path, ScriptedWindow(QUIT_KEY))

    assert image_names(tmp_path, "train") == []


def test_skip_key_moves_on_to_the_next_card(tmp_path: Path) -> None:
    run_session(tmp_path, ScriptedWindow(SKIP_KEY, RECORD_KEY, QUIT_KEY))

    expected_images = [f"red_1_p0_f{frame}.jpg" for frame in range(FRAMES_PER_POSITION)]
    assert image_names(tmp_path, "train") == expected_images


@pytest.mark.parametrize("seed", range(50))
def test_guide_box_stays_inside_the_frame(seed: int) -> None:
    box = choose_guide_box(FRAME_WIDTH, FRAME_HEIGHT, random.Random(seed))

    assert 0 <= box.x1 < box.x2 <= FRAME_WIDTH
    assert 0 <= box.y1 < box.y2 <= FRAME_HEIGHT


def test_guide_box_has_the_proportions_of_a_card() -> None:
    box = choose_guide_box(1280, 720, random.Random(0))

    width_to_height = (box.x2 - box.x1) / (box.y2 - box.y1)
    assert width_to_height == pytest.approx(CARD_WIDTH_TO_HEIGHT, abs=0.01)
