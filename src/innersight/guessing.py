"""The guessing game: guess the card you hold while blindfolded, then score your own guess."""

import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from innersight.announcement import (
    CardWatcher,
    spoken_name,
    with_too_close_warning,
)
from innersight.cards import CARD_BACK, Card, CardFace

READY_PHRASE = "The machine is ready"
NEXT_CARD_PHRASE = "Locked in. Next card"
LAST_CARD_PHRASE = "Locked in. Last card"
NO_CARD_PHRASE = "Hold up a card first"
NO_ANSWER_PHRASE = "Answer first"
SESSION_FINISHED_PHRASE = "Session finished"
# Said before the name of the card when the reading of a round is corrected.
CORRECTION_PHRASE = "Correction"

# How long after a card is first read a surer reading may still replace it. After that, another
# card in view is taken for the next card held up too early, and is ignored.
CORRECTION_SECONDS = 5.0


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

    `clock` gives the time in seconds; only the difference between two readings is used.
    With `speaks_result` the count of every answer is said when the session ends; without it
    the voice only says that the session is finished.
    """

    def __init__(
        self,
        card_count: int,
        say: Callable[[str], None],
        clock: Callable[[], float] = time.monotonic,
        speaks_result: bool = False,
    ) -> None:
        self.card_count = card_count
        self._say = say
        self._clock = clock
        self._speaks_result = speaks_result
        self._watcher = CardWatcher()
        self._card: Card | None = None
        self._round_started_at = 0.0
        self._answer: GuessOutcome | None = None
        self._rounds: list[GuessRound] = []
        say(READY_PHRASE)

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
        """Take in the cards recognized in one frame; return the card of the round if it changed.

        A card that settles in view while no round is being played starts the next round.
        The back of a card is read aloud but starts no round, as there is nothing to guess.
        While a round is being played, a surer reading may correct its card for a short time.
        On every frame that neither starts a round nor corrects its card, None is returned.

        A card held too close to the camera is still read, and the player is told to move it.
        """
        sighting = self._watcher.observe(cards)
        if self.is_finished:
            return None
        round_card, phrase = self._take_in(sighting.settled_card)
        if sighting.is_too_close_warning_due:
            # Without a new name to say, the name of the card being played is said again.
            name = spoken_name(self._card.face) if self._card else None
            phrase = with_too_close_warning(phrase or name)
        if phrase is not None:
            self._say(phrase)
        return round_card

    def _take_in(self, settled_card: Card | None) -> tuple[Card | None, str | None]:
        """Let a card that settled start or correct a round.

        Returns the card of the round if it changed, and what to say about the settled card.
        """
        if settled_card is None:
            return None, None
        if self._card is not None:
            return self._correct_card(self._card, settled_card)
        name = spoken_name(settled_card.face)
        if settled_card.face == CARD_BACK:
            return None, name
        self._card = settled_card
        self._round_started_at = self._clock()
        return settled_card, name

    def _correct_card(self, card: Card, settled_card: Card) -> tuple[Card | None, str | None]:
        """Replace the card of the round with another reading that the model is surer of.

        A card misread at a distance is often read right once it is held closer. The answer
        given so far is dropped, as it was an answer to the card that was read first.
        Returns the new card of the round and what to say, or neither if the reading is not
        taken.
        """
        is_other_card = settled_card.face not in (card.face, CARD_BACK)
        is_surer = settled_card.detection.confidence > card.detection.confidence
        is_in_time = self._clock() - self._round_started_at <= CORRECTION_SECONDS
        if not (is_other_card and is_surer and is_in_time):
            return None, None
        self._card = settled_card
        self._answer = None
        return settled_card, f"{CORRECTION_PHRASE}. {spoken_name(settled_card.face)}"

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
            return spoken_summary(self._rounds) if self._speaks_result else SESSION_FINISHED_PHRASE
        return LAST_CARD_PHRASE if cards_left == 1 else NEXT_CARD_PHRASE


def count_outcomes(rounds: Sequence[GuessRound]) -> dict[GuessOutcome, int]:
    """How many rounds ended with each outcome, with every outcome present."""
    counts = Counter(played_round.outcome for played_round in rounds)
    return {outcome: counts[outcome] for outcome in GuessOutcome}


def spoken_summary(rounds: Sequence[GuessRound]) -> str:
    """What the voice says when a session ends and the result is to be spoken."""
    counts = ", ".join(f"{outcome} {count}" for outcome, count in count_outcomes(rounds).items())
    return f"{SESSION_FINISHED_PHRASE}. {counts}."
