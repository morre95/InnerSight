"""Turn frames a card was read in into training examples, with the true card set by the user."""

import zlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

import cv2
import numpy as np

from innersight.annotation import draw_cards
from innersight.banner import add_banner
from innersight.cards import RANKS, SUIT_COLORS, Box, Card, CardFace, fixed_color
from innersight.dataset import TRAIN_SPLIT, VALIDATION_SPLIT, CardDataset, LabeledCard
from innersight.game import RoundFrame
from innersight.live_view import DOWN_KEYS, LEFT_KEYS, QUIT_KEY, RIGHT_KEYS, UP_KEYS

SAVE_KEY = ord(" ")
SKIP_KEY = ord("s")
BACK_KEY = ord("b")

# How far each arrow key steps through the ranks and through the colors.
RANK_STEPS = {**dict.fromkeys(UP_KEYS, 1), **dict.fromkeys(DOWN_KEYS, -1)}
COLOR_STEPS = {**dict.fromkeys(RIGHT_KEYS, 1), **dict.fromkeys(LEFT_KEYS, -1)}

# One collected example in this many is held back for validation, to tell afterwards whether
# newly trained weights read the collected cards better.
VALIDATION_ONE_IN = 5

# A frame from a phone held upright is narrower than the lines of the banner.
MIN_WINDOW_WIDTH = 640
KEYS_LINES = ("Up/Down: rank   Left/Right: color", "SPACE: save   S: skip   B: back   Q: finish")


class TrueCardPicker:
    """Steps through the ranks and the colors to the card that a frame really shows."""

    def __init__(self, face: CardFace) -> None:
        self._rank = face.rank
        self._suit = face.color if face.color in SUIT_COLORS else SUIT_COLORS[0]

    @property
    def face(self) -> CardFace:
        """The card chosen so far. A wild card and the back have one color, whatever is chosen."""
        return CardFace(fixed_color(self._rank) or self._suit, self._rank)

    def step_rank(self, steps: int) -> None:
        """Move through the ranks, around from the last one to the first."""
        self._rank = RANKS[(RANKS.index(self._rank) + steps) % len(RANKS)]

    def step_color(self, steps: int) -> None:
        """Move through the four colors. A rank with one color of its own stays as it is."""
        if fixed_color(self._rank) is None:
            suit_number = SUIT_COLORS.index(self._suit) + steps
            self._suit = SUIT_COLORS[suit_number % len(SUIT_COLORS)]


@dataclass(frozen=True, eq=False)
class Candidate:
    """A frame that may become a training example.

    The key tells where the frame comes from and is the same for no two frames. The card is
    what was read in the frame; the suggested face is the card the picker starts at.
    """

    key: str
    frame: np.ndarray
    card: Card
    suggested: CardFace


@dataclass(frozen=True, eq=False)
class CollectedExample:
    """A frame with the true card that the user set for it."""

    key: str
    frame: np.ndarray
    box: Box
    face: CardFace

    @property
    def name(self) -> str:
        """The color comes first, as in a recorded image, so the color measuring reads it."""
        return f"{self.face.color}_{self.face.rank}_{self.key}"

    @property
    def split(self) -> str:
        """The split depends on the key alone, so an example lands in the same one every time."""
        is_held_back = zlib.crc32(self.key.encode()) % VALIDATION_ONE_IN == 0
        return VALIDATION_SPLIT if is_held_back else TRAIN_SPLIT


@dataclass(frozen=True)
class CollectResult:
    """What the user decided. A candidate that was never decided on is in neither list."""

    saved: list[CollectedExample]
    skipped: list[Candidate]


class CollectSession:
    """Shows candidates one at a time and lets the user set the true card of each, or skip it.

    Nothing is written here: the decisions are returned, so going back and deciding again
    replaces the earlier decision.
    """

    def __init__(self, show_until_key_code: Callable[[np.ndarray], int]) -> None:
        """`show_until_key_code` displays an image and returns the full code of the next key."""
        self._show_until_key_code = show_until_key_code

    def run(self, candidates: Sequence[Candidate]) -> CollectResult:
        pickers = [TrueCardPicker(candidate.suggested) for candidate in candidates]
        is_saved: dict[int, bool] = {}
        index = 0
        while index < len(candidates):
            picker = pickers[index]
            lines = _describe(candidates[index], picker.face, index + 1, len(candidates))
            key = self._show_until_key_code(_render(candidates[index], lines))
            if key == QUIT_KEY:
                break
            picker.step_rank(RANK_STEPS.get(key, 0))
            picker.step_color(COLOR_STEPS.get(key, 0))
            if key == BACK_KEY:
                index = max(index - 1, 0)
            elif key in (SAVE_KEY, SKIP_KEY):
                is_saved[index] = key == SAVE_KEY
                index += 1
        return CollectResult(
            saved=[
                CollectedExample(
                    candidates[index].key,
                    candidates[index].frame,
                    candidates[index].card.detection.box,
                    pickers[index].face,
                )
                for index in sorted(is_saved)
                if is_saved[index]
            ],
            skipped=[candidates[index] for index in sorted(is_saved) if not is_saved[index]],
        )


def accept_suggestions(candidates: Sequence[Candidate]) -> CollectResult:
    """Decide without asking: every candidate is saved as the card it suggests."""
    return CollectResult(
        saved=[
            CollectedExample(
                candidate.key, candidate.frame, candidate.card.detection.box, candidate.suggested
            )
            for candidate in candidates
        ],
        skipped=[],
    )


def candidates_from_game(
    round_frames: Sequence[RoundFrame], session_start: datetime
) -> list[Candidate]:
    """Every round of a game as a candidate that starts at the card that was read."""
    return [
        Candidate(
            key=f"game_{session_start:%Y%m%dT%H%M%S}_r{number}",
            frame=round_frame.frame,
            card=round_frame.card,
            suggested=round_frame.card.face,
        )
        for number, round_frame in enumerate(round_frames, start=1)
    ]


def save_collected(dataset: CardDataset, examples: Sequence[CollectedExample]) -> None:
    """Write the examples into the dataset, each labeled with the rank of its true card."""
    dataset.write_config()
    for example in examples:
        label = LabeledCard(example.face.rank, example.box)
        dataset.write_example(example.split, example.name, example.frame, [label])


def _describe(
    candidate: Candidate, true_face: CardFace, number: int, total: int
) -> tuple[str, ...]:
    card = candidate.card
    return (
        f"Card {number} of {total}: read as {card.label} ({card.detection.confidence:.0%} sure)",
        f"True card: {true_face.label}",
        *KEYS_LINES,
    )


def _render(candidate: Candidate, lines: Sequence[str]) -> np.ndarray:
    """The frame with the card outlined as it was read, widened if needed, under the lines."""
    outlined = draw_cards(candidate.frame, [candidate.card])
    missing_width = max(MIN_WINDOW_WIDTH - outlined.shape[1], 0)
    widened = cv2.copyMakeBorder(outlined, 0, 0, 0, missing_width, cv2.BORDER_CONSTANT)
    return add_banner(widened, lines)
