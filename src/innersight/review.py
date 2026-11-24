"""Look through the recorded bursts and pick the ones to record again."""

from collections.abc import Callable, Sequence

import cv2
import numpy as np

from innersight.banner import add_banner
from innersight.capture import Burst
from innersight.dataset import CardDataset, LabeledCard
from innersight.live_view import QUIT_KEY

KEEP_KEY = ord(" ")
RECAPTURE_KEY = ord("r")
BACK_KEY = ord("b")

# The frames of a burst are shown side by side, scaled down to tiles.
SHEET_COLUMNS = 3
TILE_WIDTH = 426
LABEL_BOX_BGR = (0, 255, 0)
LABEL_BOX_THICKNESS = 2
KEYS_LINE = "SPACE: keep   R: re-capture   B: back   Q: finish reviewing"


class ReviewSession:
    """Shows recorded bursts one at a time and collects the ones the user rejects."""

    def __init__(self, show_until_key: Callable[[np.ndarray], int], dataset: CardDataset) -> None:
        """`show_until_key` displays an image and returns the code of the next key pressed."""
        self._show_until_key = show_until_key
        self._dataset = dataset

    def run(self, bursts: Sequence[Burst]) -> list[Burst]:
        """Return the bursts marked for re-capture, in the order they were given."""
        rejected: set[Burst] = set()
        index = 0
        while index < len(bursts):
            burst = bursts[index]
            lines = _describe_burst(burst, index + 1, len(bursts), burst in rejected)
            key = self._show_until_key(self._render_sheet(burst, lines))
            if key == QUIT_KEY:
                break
            if key == BACK_KEY:
                index = max(index - 1, 0)
            elif key == RECAPTURE_KEY:
                rejected.add(burst)
                index += 1
            elif key == KEEP_KEY:
                rejected.discard(burst)
                index += 1
        return [burst for burst in bursts if burst in rejected]

    def _render_sheet(self, burst: Burst, lines: Sequence[str]) -> np.ndarray:
        tiles = [
            _render_tile(*self._dataset.read_example(burst.split, name))
            for name in burst.example_names
        ]
        return add_banner(_arrange_in_grid(tiles), lines)


def _describe_burst(burst: Burst, number: int, total: int, is_rejected: bool) -> tuple[str, ...]:
    progress = f"Reviewing {number} of {total}"
    if is_rejected:
        progress += "  -  MARKED for re-capture"
    return (burst.title, progress, KEYS_LINE)


def _render_tile(frame_bgr: np.ndarray, cards: Sequence[LabeledCard]) -> np.ndarray:
    """The saved frame, scaled down, with a box where its label says each card is."""
    outlined = frame_bgr.copy()
    for card in cards:
        box = card.box
        cv2.rectangle(
            outlined, (box.x1, box.y1), (box.x2, box.y2), LABEL_BOX_BGR, LABEL_BOX_THICKNESS
        )
    frame_height, frame_width = frame_bgr.shape[:2]
    tile_size = (TILE_WIDTH, round(frame_height * TILE_WIDTH / frame_width))
    return cv2.resize(outlined, tile_size, interpolation=cv2.INTER_AREA)


def _arrange_in_grid(tiles: Sequence[np.ndarray]) -> np.ndarray:
    blank_tiles = [np.zeros_like(tiles[0])] * (-len(tiles) % SHEET_COLUMNS)
    padded_tiles = [*tiles, *blank_tiles]
    rows = [
        np.hstack(padded_tiles[start : start + SHEET_COLUMNS])
        for start in range(0, len(padded_tiles), SHEET_COLUMNS)
    ]
    return np.vstack(rows)
