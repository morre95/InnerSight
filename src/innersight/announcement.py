"""Decide when a card held up to the camera is announced, and how its name is spoken."""

from collections.abc import Callable, Sequence

from innersight.cards import Card, CardFace

# How many frames in a row a card must be in view, or gone, before the announcer reacts.
# It keeps a flickering detection from being announced, and a brief dropout from being
# taken for the card leaving.
STABLE_FRAME_COUNT = 5

SPOKEN_RANKS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
    "skip": "skip",
    "reverse": "reverse",
    "+2": "draw two",
    "wild": "wild",
    "+4": "draw four",
    "back": "card back",
    "shuffle": "shuffle",
    "joker": "joker",
    "customizable": "customizable",
}


def spoken_name(face: CardFace) -> str:
    """What to say for a card, such as "red seven", "wild draw four" or "card back".

    A rank the detector was trained with under another name is spoken as it is written.
    """
    return face.describe(SPOKEN_RANKS.get(face.rank, face.rank))


class CardAnnouncer:
    """Says a card's name once when it settles in view, and again only after a change."""

    def __init__(self, say: Callable[[str], None]) -> None:
        self._say = say
        self._candidate: CardFace | None = None
        self._candidate_frame_count = 0
        self._announced: CardFace | None = None

    def observe(self, cards: Sequence[Card]) -> None:
        """Take in the cards recognized in one frame. With several, the surest one counts."""
        face = max(cards, key=_confidence).face if cards else None
        if face == self._candidate:
            self._candidate_frame_count += 1
        else:
            self._candidate = face
            self._candidate_frame_count = 1

        is_settled = self._candidate_frame_count == STABLE_FRAME_COUNT
        if is_settled and face != self._announced:
            self._announced = face
            if face is not None:
                self._say(spoken_name(face))


def _confidence(card: Card) -> float:
    return card.detection.confidence
