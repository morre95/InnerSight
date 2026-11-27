"""Play the guessing game on the camera, with the answers given on the keyboard."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import numpy as np

from innersight.annotation import draw_cards
from innersight.banner import add_banner
from innersight.cards import Card
from innersight.guess_log import GuessLog
from innersight.guessing import GuessingSession, GuessOutcome
from innersight.live_view import DOWN_KEYS, LEFT_KEYS, QUIT_KEY, RIGHT_KEYS, UP_KEYS
from innersight.recognition import CardDetector, crop_box, recognize_cards

LOCK_IN_KEY = ord(" ")

KEY_OUTCOMES: dict[int, GuessOutcome] = {
    **dict.fromkeys(UP_KEYS, GuessOutcome.BOTH_RIGHT),
    **dict.fromkeys(LEFT_KEYS, GuessOutcome.COLOR_RIGHT),
    **dict.fromkeys(RIGHT_KEYS, GuessOutcome.RANK_RIGHT),
    **dict.fromkeys(DOWN_KEYS, GuessOutcome.MISS),
}

CONTROLS_LINE = "Arrows: answer   SPACE: lock in   Q: quit"


@dataclass(frozen=True, eq=False)
class RoundFrame:
    """The camera frame the card of a round was last read in, and the card as it was read."""

    frame: np.ndarray
    card: Card

    @property
    def picture(self) -> np.ndarray:
        """The card cut from its frame, as a view of the frame."""
        return crop_box(self.frame, self.card.detection.box)


def play_guessing_game(
    frames: Iterable[np.ndarray],
    show: Callable[[np.ndarray], int],
    detector: CardDetector,
    session: GuessingSession,
    guess_log: GuessLog,
) -> list[RoundFrame]:
    """Play until the session is finished or the player quits; log every round as it ends.

    `show` displays a preview frame and returns the full code of the key pressed in it.
    Returns the frame the card of every locked round was last read in, so the player can
    check afterwards what the model read.
    """
    round_frames: list[RoundFrame] = []
    round_frame = None
    for frame in frames:
        cards = recognize_cards(frame, detector)
        round_card = session.observe(cards)
        if round_card is not None:
            round_frame = RoundFrame(frame, round_card)
        key = show(add_banner(draw_cards(frame, cards), _describe_round(session)))
        if key == QUIT_KEY:
            break
        if key in KEY_OUTCOMES:
            session.give_answer(KEY_OUTCOMES[key])
        elif key == LOCK_IN_KEY:
            locked_round = session.lock_in()
            if locked_round is not None:
                guess_log.append(len(session.rounds), locked_round)
                round_frames.append(round_frame)
        if session.is_finished:
            break
    return round_frames


def _describe_round(session: GuessingSession) -> tuple[str, ...]:
    card = session.card
    card_line = (
        "Hold up a card"
        if card is None
        else f"Card: {card.label} ({card.detection.confidence:.0%} sure)"
    )
    return (
        f"Card {len(session.rounds) + 1} of {session.card_count}",
        card_line,
        f"Answer: {session.answer or '-'}",
        CONTROLS_LINE,
    )
