import itertools
from datetime import datetime
from pathlib import Path

import numpy as np
from fakes import BLACK_FRAME, ScriptedWindow

from innersight.announcement import STABLE_FRAME_COUNT
from innersight.cards import Box, Detection
from innersight.game import LOCK_IN_KEY, RoundFrame, play_guessing_game
from innersight.guess_log import GuessLog
from innersight.guessing import GuessingSession, GuessOutcome
from innersight.live_view import DOWN_KEYS, LEFT_KEYS, QUIT_KEY, RIGHT_KEYS, UP_KEYS

NO_KEY = -1
UP, LEFT, RIGHT, DOWN = UP_KEYS[0], LEFT_KEYS[0], RIGHT_KEYS[0], DOWN_KEYS[0]
# A wild card, so that its color is not read from the black camera frame.
WILD_CARD = Detection(rank="wild", confidence=0.9, box=Box(0, 0, 10, 10))
WHITE = 255
CARD_SETTLES = (NO_KEY,) * STABLE_FRAME_COUNT


class CardInEveryFrame:
    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        return [WILD_CARD]


class CardUntilTakenAway:
    """Shows the card until it has settled, then no card until its absence has settled."""

    def __init__(self) -> None:
        self._frame_number = 0

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        is_card_in_view = self._frame_number % (STABLE_FRAME_COUNT * 2) < STABLE_FRAME_COUNT
        self._frame_number += 1
        return [WILD_CARD] if is_card_in_view else []


def play(tmp_path: Path, card_count: int, detector: object, *keys: int) -> GuessingSession:
    session = GuessingSession(card_count, say=lambda phrase: None)
    guess_log = GuessLog(tmp_path / "guesses.csv", datetime(2026, 11, 25))
    frames = itertools.repeat(BLACK_FRAME)
    play_guessing_game(frames, ScriptedWindow(*keys, QUIT_KEY), detector, session, guess_log)
    return session


def outcomes(session: GuessingSession) -> list[GuessOutcome]:
    return [played_round.outcome for played_round in session.rounds]


def test_scores_a_round_with_each_arrow_key(tmp_path: Path) -> None:
    frames_until_settled = (NO_KEY,) * (STABLE_FRAME_COUNT - 1)
    keys = [
        key
        for arrow in (UP, LEFT, RIGHT, DOWN)
        for key in (*frames_until_settled, arrow, LOCK_IN_KEY, *frames_until_settled)
    ]

    session = play(tmp_path, 4, CardUntilTakenAway(), *keys)

    assert outcomes(session) == [
        GuessOutcome.BOTH_RIGHT,
        GuessOutcome.COLOR_RIGHT,
        GuessOutcome.RANK_RIGHT,
        GuessOutcome.MISS,
    ]


def test_counts_the_last_arrow_key_pressed_before_locking_in(tmp_path: Path) -> None:
    session = play(tmp_path, 1, CardInEveryFrame(), *CARD_SETTLES, DOWN, LEFT, UP, LOCK_IN_KEY)

    assert outcomes(session) == [GuessOutcome.BOTH_RIGHT]


def test_stops_when_the_chosen_number_of_cards_is_played(tmp_path: Path) -> None:
    window = ScriptedWindow(*CARD_SETTLES, UP, LOCK_IN_KEY, NO_KEY)
    session = GuessingSession(1, say=lambda phrase: None)
    guess_log = GuessLog(tmp_path / "guesses.csv", datetime(2026, 11, 25))

    play_guessing_game(
        itertools.repeat(BLACK_FRAME), window, CardInEveryFrame(), session, guess_log
    )

    assert window.frames_shown == STABLE_FRAME_COUNT + 2


def test_keeps_the_rounds_played_when_the_player_quits_early(tmp_path: Path) -> None:
    session = play(tmp_path, 5, CardInEveryFrame(), *CARD_SETTLES, UP, LOCK_IN_KEY)

    assert outcomes(session) == [GuessOutcome.BOTH_RIGHT]


def test_logs_every_round_as_it_is_locked_in(tmp_path: Path) -> None:
    play(tmp_path, 5, CardInEveryFrame(), *CARD_SETTLES, UP, LOCK_IN_KEY)

    log_lines = (tmp_path / "guesses.csv").read_text().splitlines()
    assert log_lines[1:] == ["2026-11-25T00:00:00,1,wild,0.900,both right"]


def play_one_round_on(tmp_path: Path, frame: np.ndarray) -> list[RoundFrame]:
    session = GuessingSession(1, say=lambda phrase: None)
    guess_log = GuessLog(tmp_path / "guesses.csv", datetime(2026, 11, 25))
    window = ScriptedWindow(*CARD_SETTLES, UP, LOCK_IN_KEY)
    return play_guessing_game(
        itertools.repeat(frame), window, CardInEveryFrame(), session, guess_log
    )


def test_returns_the_frame_and_the_card_of_every_locked_round(tmp_path: Path) -> None:
    gray_frame = np.full_like(BLACK_FRAME, 128)

    round_frames = play_one_round_on(tmp_path, gray_frame)

    assert [round_frame.card.detection for round_frame in round_frames] == [WILD_CARD]
    assert (round_frames[0].frame == gray_frame).all()


def test_cuts_the_picture_of_a_round_from_its_frame(tmp_path: Path) -> None:
    frame = BLACK_FRAME.copy()
    box = WILD_CARD.box
    frame[box.y1 : box.y2, box.x1 : box.x2] = WHITE

    round_frames = play_one_round_on(tmp_path, frame)

    assert round_frames[0].picture.shape == (10, 10, 3)
    assert (round_frames[0].picture == WHITE).all()


def test_returns_no_frame_of_a_card_that_was_not_locked_in(tmp_path: Path) -> None:
    session = GuessingSession(2, say=lambda phrase: None)
    guess_log = GuessLog(tmp_path / "guesses.csv", datetime(2026, 11, 25))
    window = ScriptedWindow(*CARD_SETTLES, UP, QUIT_KEY)

    round_frames = play_guessing_game(
        itertools.repeat(BLACK_FRAME), window, CardInEveryFrame(), session, guess_log
    )

    assert round_frames == []


def test_shows_the_round_and_the_answer_above_the_preview(tmp_path: Path) -> None:
    window = ScriptedWindow(NO_KEY, QUIT_KEY)
    session = GuessingSession(3, say=lambda phrase: None)
    guess_log = GuessLog(tmp_path / "guesses.csv", datetime(2026, 11, 25))

    play_guessing_game(
        itertools.repeat(BLACK_FRAME), window, CardInEveryFrame(), session, guess_log
    )

    assert window.last_frame is not None
    assert window.last_frame.shape[0] > BLACK_FRAME.shape[0]
