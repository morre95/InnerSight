"""Decide when a card held up to the camera is announced, and how its name is spoken."""

from collections.abc import Callable, Sequence

from innersight.cards import Card, CardColor, CardFace

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


class SettledCardWatcher:
    """Reports a card once when it settles in view, and again only after a change."""

    def __init__(self) -> None:
        self._candidate: CardFace | None = None
        self._candidate_frame_count = 0
        self._settled: CardFace | None = None

    def observe(self, cards: Sequence[Card]) -> Card | None:
        """Take in the cards recognized in one frame. With several, the surest one counts.

        Returns the card on the frame it settles in view, and None on every other frame.

        A card whose color could not be read is not a card that exists, such as "unknown 5".
        A frame that shows only such cards is left out, so the card is read again in the
        next frame, and neither settles under a wrong name nor counts as taken away.
        """
        readable_cards = [card for card in cards if card.color != CardColor.UNKNOWN]
        if cards and not readable_cards:
            return None
        card = max(readable_cards, key=_confidence) if readable_cards else None
        face = card.face if card else None
        if face == self._candidate:
            self._candidate_frame_count += 1
        else:
            self._candidate = face
            self._candidate_frame_count = 1

        is_settled = self._candidate_frame_count == STABLE_FRAME_COUNT
        if not is_settled or face == self._settled:
            return None
        self._settled = face
        return card


class CardAnnouncer:
    """Says a card's name once when it settles in view, and again only after a change."""

    def __init__(self, say: Callable[[str], None]) -> None:
        self._say = say
        self._watcher = SettledCardWatcher()

    def observe(self, cards: Sequence[Card]) -> None:
        """Take in the cards recognized in one frame. With several, the surest one counts."""
        card = self._watcher.observe(cards)
        if card is not None:
            self._say(spoken_name(card.face))


def _confidence(card: Card) -> float:
    return card.detection.confidence
