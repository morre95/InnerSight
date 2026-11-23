"""Domain types shared by detection, color classification and recognition."""

from dataclasses import dataclass
from enum import StrEnum


class CardColor(StrEnum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    WILD = "wild"


@dataclass(frozen=True)
class Box:
    """Pixel rectangle in a frame: (x1, y1) is the top-left corner, (x2, y2) the bottom-right."""

    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class Detection:
    """A card found in a frame, before its color is known.

    The rank is the class name the detector was trained with, such as "7" or "skip".
    """

    rank: str
    confidence: float
    box: Box


@dataclass(frozen=True)
class Card:
    """A detected card together with its color."""

    detection: Detection
    color: CardColor

    @property
    def label(self) -> str:
        return f"{self.color} {self.detection.rank}"
