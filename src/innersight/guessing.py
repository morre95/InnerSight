"""The guessing game: guess the card you hold while blindfolded, then score your own guess."""

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from innersight.announcement import SettledCardWatcher, spoken_name
from innersight.cards import CARD_BACK, Card, CardFace

FIRST_CARD_PHRASE = "Hold up your first card"
NEXT_CARD_PHRASE = "Locked in. Next card"
LAST_CARD_PHRASE = "Locked in. Last card"
NO_CARD_PHRASE = "Hold up a card first"
NO_ANSWER_PHRASE = "Answer first"


class GuessOutcome(StrEnum):
    """How a guess turned out. The value is what the voice says for it."""

    BOTH_RIGHT = "both right"
    COLOR_RIGHT = "color right"
    RANK_RIGHT = "rank right"
    MISS = "miss"


@dataclass(frozen=True)
class GuessRound:
    """One card of a session: what the model read, how sure it was, and how the guess went."""

    face: CardFace
    confidence: float
    outcome: GuessOutcome


class GuessingSession:
    """Runs the rounds of one game and speaks every step, so it can be played blindfolded.

    A round starts when a card settles in view and is read aloud. The player then answers as
    often as they like; the last answer counts once they lock it in.
    """

    def __init__(self, card_count: int, say: Callable[[str], None]) -> None:
        self.card_count = card_count
        self._say = say
        self._watcher = SettledCardWatcher()
        self._card: Card | None = None
        self._answer: GuessOutcome | None = None
        self._rounds: list[GuessRound] = []
        say(FIRST_CARD_PHRASE)

    @property
    def rounds(self) -> Sequence[GuessRound]:
        """The rounds that are locked in, in the order they were played."""
        return tuple(self._rounds)

    @property
    def card(self) -> Card | None:
        """The card of the round being played, or None while waiting for the next card."""
        return self._card

    @property
    def answer(self) -> GuessOutcome | None:
        """The latest answer in the round being played."""
        return self._answer

    @property
    def is_finished(self) -> bool:
        return len(self._rounds) == self.card_count

    def observe(self, cards: Sequence[Card]) -> Card | None:
        """Take in the cards recognized in one frame; return the card that starts a round.

        A card that settles in view while no round is being played starts the next round.
        The back of a card is read aloud but starts no round, as there is nothing to guess.
        On every frame that starts no round, None is returned.
        """
        settled_card = self._watcher.observe(cards)
        if settled_card is None or self._card is not None or self.is_finished:
            return None
        self._say(spoken_name(settled_card.face))
        if settled_card.face == CARD_BACK:
            return None
        self._card = settled_card
        return settled_card

    def give_answer(self, outcome: GuessOutcome) -> None:
        """Say the outcome, and make it the answer of the round being played.

        Between rounds it is only said, so the player can learn the controls by ear.
        """
        self._say(outcome)
        if self._card is not None:
            self._answer = outcome

    def lock_in(self) -> GuessRound | None:
        """End the round with its latest answer; return the round, or None if it is not over."""
        if self._card is None:
            self._say(NO_CARD_PHRASE)
            return None
        if self._answer is None:
            self._say(NO_ANSWER_PHRASE)
            return None
        locked_round = GuessRound(self._card.face, self._card.detection.confidence, self._answer)
        self._rounds.append(locked_round)
        self._card = None
        self._answer = None
        self._say(self._phrase_after_locking_in())
        return locked_round

    def _phrase_after_locking_in(self) -> str:
        cards_left = self.card_count - len(self._rounds)
        if cards_left == 0:
            return spoken_summary(self._rounds)
        return LAST_CARD_PHRASE if cards_left == 1 else NEXT_CARD_PHRASE


def count_outcomes(rounds: Sequence[GuessRound]) -> dict[GuessOutcome, int]:
    """How many rounds ended with each outcome, with every outcome present."""
    counts = Counter(played_round.outcome for played_round in rounds)
    return {outcome: counts[outcome] for outcome in GuessOutcome}


def spoken_summary(rounds: Sequence[GuessRound]) -> str:
    """What the voice says when a session ends."""
    counts = ", ".join(f"{outcome} {count}" for outcome, count in count_outcomes(rounds).items())
    return f"Session finished. {counts}."
