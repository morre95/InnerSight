from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from innersight.cards import RANKS, Box
from innersight.dataset import TRAIN_SPLIT, CardDataset, LabeledCard, turn_upside_down
from innersight.errors import DatasetReadError, DatasetWriteError

FRAME_HEIGHT = 100
FRAME_WIDTH = 200
SKIP_CARD_IN_THE_MIDDLE = LabeledCard(rank="skip", box=Box(50, 20, 150, 80))


def make_frame() -> np.ndarray:
    return np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)


def test_saves_the_frame_as_an_image(tmp_path: Path) -> None:
    CardDataset(tmp_path).write_example(
        TRAIN_SPLIT, "red_skip", make_frame(), [SKIP_CARD_IN_THE_MIDDLE]
    )

    saved_image = cv2.imread(str(tmp_path / "train" / "images" / "red_skip.jpg"))
    assert saved_image.shape == (FRAME_HEIGHT, FRAME_WIDTH, 3)


def test_labels_a_card_with_class_id_and_normalized_box(tmp_path: Path) -> None:
    CardDataset(tmp_path).write_example(
        TRAIN_SPLIT, "red_skip", make_frame(), [SKIP_CARD_IN_THE_MIDDLE]
    )

    label = (tmp_path / "train" / "labels" / "red_skip.txt").read_text()
    assert label == "10 0.500000 0.500000 0.500000 0.600000\n"


def test_frame_without_cards_gets_an_empty_label_file(tmp_path: Path) -> None:
    CardDataset(tmp_path).write_example(TRAIN_SPLIT, "background", make_frame(), [])

    assert (tmp_path / "train" / "labels" / "background.txt").read_text() == ""


def test_has_example_only_after_it_is_written(tmp_path: Path) -> None:
    dataset = CardDataset(tmp_path)
    was_present_before = dataset.has_example(TRAIN_SPLIT, "background")

    dataset.write_example(TRAIN_SPLIT, "background", make_frame(), [])

    assert not was_present_before
    assert dataset.has_example(TRAIN_SPLIT, "background")


def test_config_names_every_rank_by_class_id(tmp_path: Path) -> None:
    CardDataset(tmp_path).write_config()

    config = yaml.safe_load((tmp_path / "data.yaml").read_text())
    assert config == {
        "train": "train/images",
        "val": "valid/images",
        "names": dict(enumerate(RANKS)),
    }


def test_raises_dataset_write_error_when_the_directory_cannot_be_created(tmp_path: Path) -> None:
    file_in_the_way = tmp_path / "dataset"
    file_in_the_way.write_text("")

    with pytest.raises(DatasetWriteError):
        CardDataset(file_in_the_way).write_example(TRAIN_SPLIT, "background", make_frame(), [])


def test_reads_back_the_cards_it_wrote(tmp_path: Path) -> None:
    dataset = CardDataset(tmp_path)
    dataset.write_example(TRAIN_SPLIT, "red_skip", make_frame(), [SKIP_CARD_IN_THE_MIDDLE])

    _, cards = dataset.read_example(TRAIN_SPLIT, "red_skip")

    assert cards == [SKIP_CARD_IN_THE_MIDDLE]


def test_reads_back_the_frame_it_wrote(tmp_path: Path) -> None:
    dataset = CardDataset(tmp_path)
    dataset.write_example(TRAIN_SPLIT, "background", make_frame(), [])

    frame, _ = dataset.read_example(TRAIN_SPLIT, "background")

    assert frame.shape == (FRAME_HEIGHT, FRAME_WIDTH, 3)


def test_raises_dataset_read_error_for_an_example_that_does_not_exist(tmp_path: Path) -> None:
    with pytest.raises(DatasetReadError):
        CardDataset(tmp_path).read_example(TRAIN_SPLIT, "missing")


def test_turns_a_frame_upside_down_with_the_card_still_labeled_where_it_is() -> None:
    white = 255
    card_in_the_top_left = LabeledCard(rank="6", box=Box(10, 5, 60, 45))
    frame = make_frame()
    frame[5:45, 10:60] = white

    turned_frame, turned_cards = turn_upside_down(frame, [card_in_the_top_left])

    assert turned_cards == [LabeledCard(rank="6", box=Box(140, 55, 190, 95))]
    assert (turned_frame[55:95, 140:190] == white).all()
    assert turned_frame.sum() == frame.sum()
