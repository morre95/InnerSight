"""Decide when a card held up to the camera is announced, and how its name is spoken."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from innersight.cards import Card, CardColor, CardFace

# How many frames in a row a card must be in view, or gone, before the announcer reacts.
# It keeps a flickering detection from being announced, and a brief dropout from being
# taken for the card leaving.
STABLE_FRAME_COUNT = 5

TOO_CLOSE_PHRASE = "Too close"

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


class SettlingValue[Value]:
    """Follows a value that is read anew in every frame, and tells when it has settled.

    A value settles when it has been the same for STABLE_FRAME_COUNT frames in a row.
    """

    def __init__(self, initial: Value) -> None:
        self._candidate = initial
        self._candidate_frame_count = 0
        self._settled = initial

    @property
    def settled(self) -> Value:
        """The value that last settled."""
        return self._settled

    def observe(self, value: Value) -> bool:
        """Take in the value of one frame; tell whether it settles on something new in it."""
        if value == self._candidate:
            self._candidate_frame_count += 1
        else:
            self._candidate = value
            self._candidate_frame_count = 1

        is_settled = self._candidate_frame_count == STABLE_FRAME_COUNT
        if not is_settled or value == self._settled:
            return False
        self._settled = value
        return True


@dataclass(frozen=True)
class CardSighting:
    """What a CardWatcher makes of one frame."""

    settled_card: Card | None
    """The card that settled in view in this frame, or None in every other frame."""

    is_too_close_warning_due: bool
    """True in the frame a card has settled too close to the camera."""


class CardWatcher:
    """Follows the card held up to the camera from frame to frame.

    It reports a card once when it settles in view, and again only after a change. It tells
    once when a card is held too close to the camera, and again only after it was not.
    """

    def __init__(self) -> None:
        self._face = SettlingValue[CardFace | None](None)
        self._is_too_close = SettlingValue(False)

    @property
    def settled(self) -> CardFace | None:
        """The card that last settled in view, or None when no card is in view."""
        return self._face.settled

    def observe(self, cards: Sequence[Card]) -> CardSighting:
        """Take in the cards recognized in one frame. With several, the surest one counts."""
        return CardSighting(self._settle_card(cards), self._settle_too_close(cards))

    def _settle_card(self, cards: Sequence[Card]) -> Card | None:
        """Return the card on the frame it settles in view, and None on every other frame.

        A card whose color could not be read is not a card that exists, such as "unknown 5".
        A frame that shows only such cards is left out, so the card is read again in the
        next frame, and neither settles under a wrong name nor counts as taken away.
        """
        readable_cards = [card for card in cards if card.color != CardColor.UNKNOWN]
        if cards and not readable_cards:
            return None
        card = max(readable_cards, key=_confidence, default=None)
        has_settled = self._face.observe(card.face if card else None)
        return card if has_settled else None

    def _settle_too_close(self, cards: Sequence[Card]) -> bool:
        """Return True on the frame the card has settled too close, and False on every other.

        A card too close is often one whose color cannot be read, and it needs the warning
        all the same. So here the surest of all the cards counts, readable or not.
        """
        card = max(cards, key=_confidence, default=None)
        is_too_close = card is not None and card.is_too_close
        return self._is_too_close.observe(is_too_close) and is_too_close


def with_too_close_warning(phrase: str | None) -> str:
    """Add the warning that the card is too close to what is said, if anything is.

    A new phrase cuts off the one being spoken. So when the warning comes while the name of
    the card is spoken, it has to say the name again, or the player never hears it.
    """
    return TOO_CLOSE_PHRASE if phrase is None else f"{phrase}. {TOO_CLOSE_PHRASE}"


class CardAnnouncer:
    """Says a card's name once when it settles in view, and again only after a change.

    It also says when the card is held too close to the camera.
    """

    def __init__(self, say: Callable[[str], None]) -> None:
        self._say = say
        self._watcher = CardWatcher()

    def observe(self, cards: Sequence[Card]) -> None:
        """Take in the cards recognized in one frame. With several, the surest one counts."""
        sighting = self._watcher.observe(cards)
        if sighting.is_too_close_warning_due:
            face = self._watcher.settled
            self._say(with_too_close_warning(spoken_name(face) if face else None))
        elif sighting.settled_card is not None:
            self._say(spoken_name(sighting.settled_card.face))


def _confidence(card: Card) -> float:
    return card.detection.confidence
