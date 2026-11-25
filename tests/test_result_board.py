import numpy as np

from innersight.cards import CardColor, CardFace
from innersight.guessing import GuessOutcome, GuessRound
from innersight.result_board import (
    BOARD_WIDTH,
    CARD_ROWS_PER_COLUMN,
    card_rows,
    draw_result_board,
    summary_rows,
)

ROUNDS = [
    GuessRound(CardFace(CardColor.RED, "7"), 0.934, GuessOutcome.BOTH_RIGHT),
    GuessRound(CardFace(CardColor.BLUE, "skip"), 0.61, GuessOutcome.MISS),
    GuessRound(CardFace(CardColor.WILD, "+4"), 0.8, GuessOutcome.MISS),
    GuessRound(CardFace(CardColor.GREEN, "2"), 0.75, GuessOutcome.COLOR_RIGHT),
]
PURE_RED_BGR = (0, 0, 255)
PURE_GREEN_BGR = (0, 255, 0)


def make_picture(color_bgr: tuple[int, int, int] = PURE_RED_BGR) -> np.ndarray:
    """A picture in the upright shape of a card."""
    return np.full((90, 60, 3), color_bgr, dtype=np.uint8)


def has_color(board: np.ndarray, color_bgr: tuple[int, int, int]) -> bool:
    return bool((board == color_bgr).all(axis=2).any())


def test_counts_every_outcome_with_its_share_of_the_cards() -> None:
    rows = summary_rows(ROUNDS)

    assert ("", "both right", "1", "25%") in rows
    assert ("", "color right", "1", "25%") in rows
    assert ("", "rank right", "0", "0%") in rows
    assert ("", "miss", "2", "50%") in rows


def test_lists_every_card_with_the_confidence_of_the_model_and_the_outcome() -> None:
    rows = card_rows(ROUNDS)

    assert rows == [
        ("1", "red 7", "93%", "both right"),
        ("2", "blue skip", "61%", "miss"),
        ("3", "wild +4", "80%", "miss"),
        ("4", "green 2", "75%", "color right"),
    ]


def test_draws_a_board_that_grows_with_the_number_of_cards() -> None:
    short_board = draw_result_board(ROUNDS[:1], [make_picture()])
    long_board = draw_result_board(ROUNDS, [make_picture()] * len(ROUNDS))

    assert short_board.shape[1] == long_board.shape[1] == BOARD_WIDTH
    assert long_board.shape[0] > short_board.shape[0]
    assert long_board.any()


def test_shows_the_picture_of_every_card() -> None:
    pictures = [make_picture(PURE_RED_BGR), make_picture(PURE_GREEN_BGR)]

    board = draw_result_board(ROUNDS[:2], pictures)

    assert has_color(board, PURE_RED_BGR)
    assert has_color(board, PURE_GREEN_BGR)


def test_continues_a_long_session_in_a_new_column_instead_of_growing_taller() -> None:
    one_column = ROUNDS[:1] * CARD_ROWS_PER_COLUMN
    two_columns = one_column * 2

    narrow_board = draw_result_board(one_column, [make_picture()] * len(one_column))
    wide_board = draw_result_board(two_columns, [make_picture()] * len(two_columns))

    assert wide_board.shape[0] == narrow_board.shape[0]
    assert wide_board.shape[1] > narrow_board.shape[1]
