"""Domain types shared by detection, color classification, recognition and capture."""

from dataclasses import dataclass
from enum import StrEnum


class CardColor(StrEnum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    WILD = "wild"
    BACK = "back"


SUIT_COLORS = (CardColor.RED, CardColor.YELLOW, CardColor.GREEN, CardColor.BLUE)

COLORED_RANKS = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "skip", "reverse", "+2")
WILD_RANKS = ("wild", "+4")
BACK_RANK = "back"

# The detector's classes, in class-id order. New classes go last, so that the class ids in
# label files that are already recorded keep their meaning.
RANKS = (*COLORED_RANKS, *WILD_RANKS, BACK_RANK)


@dataclass(frozen=True)
class CardFace:
    """What one side of a card shows: one of the 54 designs in a UNO deck, or the back."""

    color: CardColor
    rank: str

    @property
    def label(self) -> str:
        """Human-readable name, such as "red 7", "wild", "wild +4" or "back"."""
        return self.describe(self.rank)

    def describe(self, rank_wording: str) -> str:
        """Name the card with the given wording for its rank, such as "seven" for "7"."""
        # The plain wild card and the back have the same word as both rank and color.
        if self.rank == self.color:
            return rank_wording
        return f"{self.color} {rank_wording}"


DECK: tuple[CardFace, ...] = (
    *(CardFace(color, rank) for color in SUIT_COLORS for rank in COLORED_RANKS),
    *(CardFace(CardColor.WILD, rank) for rank in WILD_RANKS),
)

# Every card has the same back, so it is not one of the designs in the deck.
CARD_BACK = CardFace(CardColor.BACK, BACK_RANK)


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
