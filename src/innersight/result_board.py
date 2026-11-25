"""Show how a guessing session went: the count of every outcome, then every card."""

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
COLUMN_OFFSETS = (TEXT_MARGIN, 60, 300, 400)
CLOSE_HINT = "Press any key to close"

Row = tuple[str, ...]


def result_rows(rounds: Sequence[GuessRound]) -> list[Row]:
    """The rows of the board: a title, the count of every outcome, then one row for each card."""
    rows: list[Row] = [(f"Session result: {len(rounds)} cards",), ()]
    for outcome, count in count_outcomes(rounds).items():
        share = f"{count / len(rounds):.0%}" if rounds else "-"
        rows.append(("", outcome, str(count), share))
    rows += [(), ("#", "Card read", "Sure", "Outcome")]
    for number, played_round in enumerate(rounds, start=1):
        confidence = f"{played_round.confidence:.0%}"
        rows.append((str(number), played_round.face.label, confidence, played_round.outcome))
    return rows


def draw_result_board(rounds: Sequence[GuessRound]) -> np.ndarray:
    """Return an image of the result board."""
    rows = [*result_rows(rounds), (), (CLOSE_HINT,)]
    height = TEXT_LINE_HEIGHT * len(rows) + TEXT_MARGIN * 2
    board = np.zeros((height, BOARD_WIDTH, 3), dtype=np.uint8)
    for row_number, row in enumerate(rows, start=1):
        for offset, text in zip(COLUMN_OFFSETS, row, strict=False):
            origin = (offset, TEXT_LINE_HEIGHT * row_number)
            cv2.putText(board, text, origin, TEXT_FONT, TEXT_SCALE, TEXT_BGR, TEXT_THICKNESS)
    return board
