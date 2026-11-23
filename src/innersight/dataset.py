"""Store labeled frames as a YOLO detection dataset that Ultralytics can train on."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import yaml

from innersight.cards import RANKS, Box
from innersight.errors import DatasetWriteError

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

    def write_example(
        self, split: str, name: str, frame_bgr: np.ndarray, cards: Sequence[LabeledCard]
    ) -> None:
        """Save the frame and its labels. A frame without cards becomes a background example."""
        image_file = self._image_file(split, name)
        label_file = self._directory / split / "labels" / f"{name}.txt"
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

    def _image_file(self, split: str, name: str) -> Path:
        return self._directory / split / "images" / f"{name}.jpg"


def _format_label_line(card: LabeledCard, frame_width: int, frame_height: int) -> str:
    """YOLO label: class id, then box center and size as fractions of the frame."""
    box = card.box
    x_center = (box.x1 + box.x2) / 2 / frame_width
    y_center = (box.y1 + box.y2) / 2 / frame_height
    width = (box.x2 - box.x1) / frame_width
    height = (box.y2 - box.y1) / frame_height
    class_id = RANKS.index(card.rank)
    return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n"
