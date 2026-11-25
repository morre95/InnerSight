"""Play the guessing game on the camera, with the answers given on the keyboard."""

from collections.abc import Callable, Iterable

import numpy as np

from innersight.annotation import draw_cards
from innersight.banner import add_banner
from innersight.guess_log import GuessLog
from innersight.guessing import GuessingSession, GuessOutcome
from innersight.live_view import QUIT_KEY
from innersight.recognition import CardDetector, crop_box, recognize_cards

LOCK_IN_KEY = ord(" ")

# The full key codes of the arrow keys differ between systems: Linux, Windows, macOS.
UP_KEYS = (65362, 2490368, 63232)
LEFT_KEYS = (65361, 2424832, 63234)
RIGHT_KEYS = (65363, 2555904, 63235)
DOWN_KEYS = (65364, 2621440, 63233)

KEY_OUTCOMES: dict[int, GuessOutcome] = {
    **dict.fromkeys(UP_KEYS, GuessOutcome.BOTH_RIGHT),
    **dict.fromkeys(LEFT_KEYS, GuessOutcome.COLOR_RIGHT),
    **dict.fromkeys(RIGHT_KEYS, GuessOutcome.RANK_RIGHT),
    **dict.fromkeys(DOWN_KEYS, GuessOutcome.MISS),
}

CONTROLS_LINE = "Arrows: answer   SPACE: lock in   Q: quit"


def play_guessing_game(
    frames: Iterable[np.ndarray],
    show: Callable[[np.ndarray], int],
    detector: CardDetector,
    session: GuessingSession,
    guess_log: GuessLog,
) -> list[np.ndarray]:
    """Play until the session is finished or the player quits; log every round as it ends.

    `show` displays a preview frame and returns the full code of the key pressed in it.
    Returns a picture of the card of every locked round, cut from the frame it was read in,
    so the player can check afterwards what the model read.
    """
    pictures: list[np.ndarray] = []
    picture = None
    for frame in frames:
        cards = recognize_cards(frame, detector)
        round_card = session.observe(cards)
        if round_card is not None:
            # A copy, as the crop alone would keep the whole frame in memory.
            picture = crop_box(frame, round_card.detection.box).copy()
        key = show(add_banner(draw_cards(frame, cards), _describe_round(session)))
        if key == QUIT_KEY:
            break
        if key in KEY_OUTCOMES:
            session.give_answer(KEY_OUTCOMES[key])
        elif key == LOCK_IN_KEY:
            locked_round = session.lock_in()
            if locked_round is not None:
                guess_log.append(len(session.rounds), locked_round)
                pictures.append(picture)
        if session.is_finished:
            break
    return pictures


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
