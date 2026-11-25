"""Show how a guessing session went: the count of every outcome, then every card."""

import math
from collections.abc import Sequence

import cv2
import numpy as np

from innersight.banner import (
    TEXT_BGR,
    TEXT_FONT,
    TEXT_LINE_HEIGHT,
    TEXT_MARGIN,
    TEXT_SCALE,
    TEXT_THICKNESS,
)
from innersight.guessing import GuessRound, count_outcomes

BOARD_WIDTH = 640
# Where the columns of a row start, so that the rows line up in a font that is not monospaced.
SUMMARY_OFFSETS = (TEXT_MARGIN, 60, 300, 400)
# The picture of a card goes between its number and its name.
CARD_OFFSETS = (TEXT_MARGIN, 162, 377, 452)
CARD_HEADER = ("#", "Card read", "Sure", "Outcome")
PICTURE_OFFSET = 50
# A picture is fitted into a square with this side, in pixels.
PICTURE_SIZE = 96
CARD_ROW_HEIGHT = PICTURE_SIZE + 8
# A longer session continues in a new column to the right, so the board fits on the screen.
CARD_ROWS_PER_COLUMN = 6
CARD_COLUMN_WIDTH = 612
# How far below the middle of a card row the baseline of its text is.
TEXT_BASELINE_DROP = 6
CLOSE_HINT = "Press any key to close"

Row = tuple[str, ...]


def summary_rows(rounds: Sequence[GuessRound]) -> list[Row]:
    """The top of the board: a title, then the count of every outcome."""
    rows: list[Row] = [(f"Session result: {len(rounds)} cards",), ()]
    for outcome, count in count_outcomes(rounds).items():
        share = f"{count / len(rounds):.0%}" if rounds else "-"
        rows.append(("", outcome, str(count), share))
    return rows


def card_rows(rounds: Sequence[GuessRound]) -> list[Row]:
    """One row for each card: its number, what the model read, how sure it was, the outcome."""
    return [
        (
            str(number),
            played_round.face.label,
            f"{played_round.confidence:.0%}",
            played_round.outcome,
        )
        for number, played_round in enumerate(rounds, start=1)
    ]


def draw_result_board(rounds: Sequence[GuessRound], pictures: Sequence[np.ndarray]) -> np.ndarray:
    """Return an image of the result board, with the picture of every card beside its row."""
    summary = summary_rows(rounds)
    column_count = max(1, math.ceil(len(rounds) / CARD_ROWS_PER_COLUMN))
    rows_per_column = math.ceil(len(rounds) / column_count)
    # The summary, an empty line, then the header of the card table.
    header_baseline = TEXT_LINE_HEIGHT * (len(summary) + 2)
    table_top = header_baseline + TEXT_MARGIN
    hint_baseline = table_top + CARD_ROW_HEIGHT * rows_per_column + TEXT_LINE_HEIGHT
    width = max(BOARD_WIDTH, CARD_COLUMN_WIDTH * column_count)
    board = np.zeros((hint_baseline + TEXT_MARGIN, width, 3), dtype=np.uint8)

    for row_number, row in enumerate(summary, start=1):
        _put_row(board, row, SUMMARY_OFFSETS, 0, TEXT_LINE_HEIGHT * row_number)
    for column in range(column_count):
        _put_row(board, CARD_HEADER, CARD_OFFSETS, CARD_COLUMN_WIDTH * column, header_baseline)
    card_table = zip(card_rows(rounds), pictures, strict=True)
    for card_number, (row, picture) in enumerate(card_table):
        column, row_in_column = divmod(card_number, rows_per_column)
        left = CARD_COLUMN_WIDTH * column
        top = table_top + CARD_ROW_HEIGHT * row_in_column
        _put_row(board, row, CARD_OFFSETS, left, top + PICTURE_SIZE // 2 + TEXT_BASELINE_DROP)
        _put_picture(board, picture, left + PICTURE_OFFSET, top)
    _put_row(board, (CLOSE_HINT,), SUMMARY_OFFSETS, 0, hint_baseline)
    return board


def _put_row(board: np.ndarray, row: Row, offsets: Sequence[int], left: int, baseline: int) -> None:
    for offset, text in zip(offsets, row, strict=False):
        origin = (left + offset, baseline)
        cv2.putText(board, text, origin, TEXT_FONT, TEXT_SCALE, TEXT_BGR, TEXT_THICKNESS)


def _put_picture(board: np.ndarray, picture: np.ndarray, left: int, top: int) -> None:
    """Draw the picture, scaled to fit, in the middle of the square at (left, top)."""
    height, width = picture.shape[:2]
    scale = PICTURE_SIZE / max(height, width)
    fitted_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    fitted = cv2.resize(picture, fitted_size, interpolation=cv2.INTER_AREA)
    fitted_width, fitted_height = fitted_size
    x = left + (PICTURE_SIZE - fitted_width) // 2
    y = top + (PICTURE_SIZE - fitted_height) // 2
    board[y : y + fitted_height, x : x + fitted_width] = fitted
