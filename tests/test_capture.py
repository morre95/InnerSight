import random
from pathlib import Path

import cv2
import numpy as np
import pytest
from fakes import BLACK_FRAME, FRAME_HEIGHT, FRAME_WIDTH, ScriptedWindow, record_bursts

from innersight.capture import (
    ALL_BURSTS,
    CAPTURE_STEPS,
    CARD_WIDTH_TO_HEIGHT,
    FRAMES_PER_POSITION,
    POSITIONS_PER_STEP,
    RECORD_KEY,
    SKIP_KEY,
    choose_guide_box,
)
from innersight.cards import RANKS
from innersight.dataset import CardDataset
from innersight.live_view import QUIT_KEY

FRAMES_PER_STEP_IN_TRAIN = (POSITIONS_PER_STEP - 1) * FRAMES_PER_POSITION
RED_ONE_SECOND_POSITION = ALL_BURSTS[POSITIONS_PER_STEP + 1]


def image_names(dataset_dir: Path, split: str) -> list[str]:
    return sorted(image.name for image in (dataset_dir / split / "images").glob("*.jpg"))


@pytest.fixture(scope="module")
def fully_recorded_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    dataset_dir = tmp_path_factory.mktemp("dataset")
    record_bursts(dataset_dir, ALL_BURSTS)
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


def test_labels_a_card_back_frame_as_the_back(fully_recorded_dir: Path) -> None:
    label = (fully_recorded_dir / "train" / "labels" / "card_back_p0_f0.txt").read_text()

    class_id = int(label.split()[0])
    assert RANKS[class_id] == "back"


def test_labels_background_frames_with_no_card(fully_recorded_dir: Path) -> None:
    label = (fully_recorded_dir / "train" / "labels" / "background_p0_f0.txt").read_text()

    assert label == ""


def test_every_burst_counts_as_recorded_after_a_full_session(fully_recorded_dir: Path) -> None:
    dataset = CardDataset(fully_recorded_dir)

    assert all(burst.is_recorded_in(dataset) for burst in ALL_BURSTS)


def test_no_burst_counts_as_recorded_in_an_empty_dataset(tmp_path: Path) -> None:
    dataset = CardDataset(tmp_path)

    assert not any(burst.is_recorded_in(dataset) for burst in ALL_BURSTS)


def test_records_only_the_bursts_it_is_given(tmp_path: Path) -> None:
    record_bursts(tmp_path, [RED_ONE_SECOND_POSITION])

    expected_images = [f"red_1_p1_f{frame}.jpg" for frame in range(FRAMES_PER_POSITION)]
    assert image_names(tmp_path, "train") == expected_images


def test_recording_a_burst_again_replaces_its_frames(tmp_path: Path) -> None:
    white_frame = np.full_like(BLACK_FRAME, 255)
    record_bursts(tmp_path, [RED_ONE_SECOND_POSITION], camera_frame=BLACK_FRAME)

    record_bursts(tmp_path, [RED_ONE_SECOND_POSITION], camera_frame=white_frame)

    saved_frame = cv2.imread(str(tmp_path / "train" / "images" / "red_1_p1_f0.jpg"))
    assert saved_frame.mean() > 250


def test_quit_key_stops_before_anything_is_recorded(tmp_path: Path) -> None:
    record_bursts(tmp_path, ALL_BURSTS, ScriptedWindow(QUIT_KEY))

    assert image_names(tmp_path, "train") == []


def test_skip_key_skips_every_position_of_that_card(tmp_path: Path) -> None:
    record_bursts(tmp_path, ALL_BURSTS, ScriptedWindow(SKIP_KEY, RECORD_KEY, QUIT_KEY))

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
