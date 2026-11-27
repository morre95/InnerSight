"""Store labeled frames as a YOLO detection dataset that Ultralytics can train on."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import yaml

from innersight.cards import RANKS, Box
from innersight.errors import DatasetReadError, DatasetWriteError

TRAIN_SPLIT = "train"
VALIDATION_SPLIT = "valid"
CONFIG_FILE_NAME = "data.yaml"


@dataclass(frozen=True)
class LabeledCard:
    """A card whose rank and position in a frame are known."""

    rank: str
    box: Box


class CardDataset:
    """A dataset directory laid out as <split>/images and <split>/labels next to data.yaml."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def write_config(self) -> None:
        """Write data.yaml. Its paths are relative, so Ultralytics resolves them from the file."""
        config = {
            "train": f"{TRAIN_SPLIT}/images",
            "val": f"{VALIDATION_SPLIT}/images",
            "names": dict(enumerate(RANKS)),
        }
        config_file = self._directory / CONFIG_FILE_NAME
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            config_file.write_text(yaml.safe_dump(config, sort_keys=False))
        except OSError as error:
            raise DatasetWriteError(f"Could not write {config_file}: {error}") from error

    def has_example(self, split: str, name: str) -> bool:
        return self._image_file(split, name).is_file()

    def example_names(self, split: str) -> list[str]:
        """The names of all examples in the split, recorded and collected alike, in order."""
        image_dir = self._image_file(split, "any").parent
        return sorted(image_file.stem for image_file in image_dir.glob("*.jpg"))

    def write_example(
        self, split: str, name: str, frame_bgr: np.ndarray, cards: Sequence[LabeledCard]
    ) -> None:
        """Save the frame and its labels. A frame without cards becomes a background example."""
        image_file = self._image_file(split, name)
        label_file = self._label_file(split, name)
        frame_height, frame_width = frame_bgr.shape[:2]
        label_lines = [_format_label_line(card, frame_width, frame_height) for card in cards]
        try:
            image_file.parent.mkdir(parents=True, exist_ok=True)
            label_file.parent.mkdir(parents=True, exist_ok=True)
            label_file.write_text("".join(label_lines))
            is_image_written = cv2.imwrite(str(image_file), frame_bgr)
        except OSError as error:
            raise DatasetWriteError(f"Could not write {image_file}: {error}") from error
        if not is_image_written:
            raise DatasetWriteError(f"Could not write {image_file}")

    def read_example(self, split: str, name: str) -> tuple[np.ndarray, list[LabeledCard]]:
        """Load a saved frame and the cards its label file places in it."""
        image_file = self._image_file(split, name)
        label_file = self._label_file(split, name)
        frame_bgr = cv2.imread(str(image_file))
        if frame_bgr is None:
            raise DatasetReadError(f"Could not read {image_file}")
        try:
            label_lines = label_file.read_text().splitlines()
        except OSError as error:
            raise DatasetReadError(f"Could not read {label_file}: {error}") from error
        frame_height, frame_width = frame_bgr.shape[:2]
        return frame_bgr, [
            _parse_label_line(line, frame_width, frame_height) for line in label_lines
        ]

    def _image_file(self, split: str, name: str) -> Path:
        return self._directory / split / "images" / f"{name}.jpg"

    def _label_file(self, split: str, name: str) -> Path:
        return self._directory / split / "labels" / f"{name}.txt"


def turn_upside_down(
    frame_bgr: np.ndarray, cards: Sequence[LabeledCard]
) -> tuple[np.ndarray, list[LabeledCard]]:
    """Turn a labeled frame half a turn, as if every card in it were held upside down.

    A card that is turned keeps its rank, so a turned frame is a true example of it. The
    detector needs such examples of a 6 and a 9, to learn that the line under the digit tells
    them apart, and not the shape of the digit.
    """
    frame_height, frame_width = frame_bgr.shape[:2]
    turned_cards = [
        LabeledCard(
            card.rank,
            Box(
                x1=frame_width - card.box.x2,
                y1=frame_height - card.box.y2,
                x2=frame_width - card.box.x1,
                y2=frame_height - card.box.y1,
            ),
        )
        for card in cards
    ]
    return cv2.rotate(frame_bgr, cv2.ROTATE_180), turned_cards


def _format_label_line(card: LabeledCard, frame_width: int, frame_height: int) -> str:
    """YOLO label: class id, then box center and size as fractions of the frame."""
    box = card.box
    x_center = (box.x1 + box.x2) / 2 / frame_width
    y_center = (box.y1 + box.y2) / 2 / frame_height
    width = (box.x2 - box.x1) / frame_width
    height = (box.y2 - box.y1) / frame_height
    class_id = RANKS.index(card.rank)
    return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n"


def _parse_label_line(line: str, frame_width: int, frame_height: int) -> LabeledCard:
    class_id, *fractions = line.split()
    x_center, y_center, width, height = (float(fraction) for fraction in fractions)
    box = Box(
        x1=round((x_center - width / 2) * frame_width),
        y1=round((y_center - height / 2) * frame_height),
        x2=round((x_center + width / 2) * frame_width),
        y2=round((y_center + height / 2) * frame_height),
    )
    return LabeledCard(RANKS[int(class_id)], box)
