"""Domain types shared by detection, color classification, recognition and capture."""

from dataclasses import dataclass
from enum import StrEnum


class CardColor(StrEnum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    WILD = "wild"


COLORED_RANKS = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "skip", "reverse", "+2")
WILD_RANKS = ("wild", "+4")

# The detector's classes, in class-id order.
RANKS = COLORED_RANKS + WILD_RANKS


@dataclass(frozen=True)
class CardFace:
    """One of the 54 distinct card designs in a UNO deck."""

    color: CardColor
    rank: str

    @property
    def label(self) -> str:
        """Human-readable name, such as "red 7", "wild" or "wild +4"."""
        return self.describe(self.rank)

    def describe(self, rank_wording: str) -> str:
        """Name the card with the given wording for its rank, such as "seven" for "7"."""
        if self.rank == self.color:  # the plain wild card has "wild" as both rank and color
            return rank_wording
        return f"{self.color} {rank_wording}"


DECK: tuple[CardFace, ...] = (
    *(
        CardFace(color, rank)
        for color in CardColor
        if color is not CardColor.WILD
        for rank in COLORED_RANKS
    ),
    *(CardFace(CardColor.WILD, rank) for rank in WILD_RANKS),
)


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
    def face(self) -> CardFace:
        return CardFace(self.color, self.detection.rank)

    @property
    def label(self) -> str:
        return self.face.label
