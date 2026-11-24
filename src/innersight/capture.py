"""Record a labeled training dataset by holding up cards to the camera, one at a time."""

import itertools
import random
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from innersight.banner import add_banner
from innersight.cards import BACK_RANK, DECK, Box
from innersight.dataset import TRAIN_SPLIT, VALIDATION_SPLIT, CardDataset, LabeledCard
from innersight.live_view import QUIT_KEY

RECORD_KEY = ord(" ")
SKIP_KEY = ord("s")

# Every step is recorded at several places in the frame, with a short burst of frames at each.
POSITIONS_PER_STEP = 6
FRAMES_PER_POSITION = 5
# Saving every fifth camera frame keeps the frames of one burst from being near-identical.
BURST_FRAME_STRIDE = 5

# A UNO card is 56 mm wide and 87 mm tall.
CARD_WIDTH_TO_HEIGHT = 56 / 87
MIN_GUIDE_HEIGHT_FRACTION = 0.4
MAX_GUIDE_HEIGHT_FRACTION = 0.85

GUIDE_WAITING_BGR = (0, 255, 0)
GUIDE_RECORDING_BGR = (0, 0, 255)
GUIDE_THICKNESS = 2
FLIP_HORIZONTALLY = 1
RECORDING_LINES = ("Recording...",)


@dataclass(frozen=True)
class CaptureStep:
    """One thing to show the camera: a card, or no card at all when the rank is None."""

    name: str
    title: str
    prompt: str
    rank: str | None


CAPTURE_STEPS: tuple[CaptureStep, ...] = (
    *(
        CaptureStep(
            name=f"{face.color}_{face.rank}",
            title=face.label,
            prompt=f"Hold up: {face.label}",
            rank=face.rank,
        )
        for face in DECK
    ),
    CaptureStep(
        name="card_back",
        title="card back",
        prompt="Hold up: the back of any card",
        rank=BACK_RANK,
    ),
    CaptureStep(
        name="background",
        title="no card",
        prompt="Show no card: only you, your hands, the room",
        rank=None,
    ),
)


@dataclass(frozen=True)
class Burst:
    """The frames recorded for one capture step at one place in the picture."""

    step: CaptureStep
    position: int

    @property
    def title(self) -> str:
        return f"{self.step.title}, position {self.position + 1} of {POSITIONS_PER_STEP}"

    @property
    def split(self) -> str:
        """The last position of every step is held back for validation.

        Splitting by position keeps the near-identical frames of one burst in the same split.
        """
        return VALIDATION_SPLIT if self.position == POSITIONS_PER_STEP - 1 else TRAIN_SPLIT

    @property
    def example_names(self) -> tuple[str, ...]:
        return tuple(
            f"{self.step.name}_p{self.position}_f{frame}" for frame in range(FRAMES_PER_POSITION)
        )

    def is_recorded_in(self, dataset: CardDataset) -> bool:
        return all(dataset.has_example(self.split, name) for name in self.example_names)


ALL_BURSTS: tuple[Burst, ...] = tuple(
    Burst(step, position) for step in CAPTURE_STEPS for position in range(POSITIONS_PER_STEP)
)


class CaptureSession:
    """Walks the user through recording bursts with the camera."""

    def __init__(
        self,
        frames: Iterator[np.ndarray],
        show: Callable[[np.ndarray], int],
        dataset: CardDataset,
        rng: random.Random,
    ) -> None:
        """`show` displays a preview frame and returns the code of the key pressed in it."""
        self._frames = frames
        self._show = show
        self._dataset = dataset
        self._rng = rng

    def record(self, bursts: Sequence[Burst]) -> None:
        """Record the bursts in order, replacing the frames a burst already has."""
        self._dataset.write_config()
        frame_height, frame_width = next(self._frames).shape[:2]
        skipped_step = None
        for number, burst in enumerate(bursts, start=1):
            if burst.step == skipped_step:
                continue
            target = self._choose_target(burst.step, frame_width, frame_height)
            key = self._wait_for_key(target, _describe_burst(burst, number, len(bursts)))
            if key == QUIT_KEY:
                return
            if key == SKIP_KEY:
                skipped_step = burst.step
                continue
            self._record_burst(burst, target)

    def _choose_target(
        self, step: CaptureStep, frame_width: int, frame_height: int
    ) -> LabeledCard | None:
        if step.rank is None:
            return None
        return LabeledCard(step.rank, choose_guide_box(frame_width, frame_height, self._rng))

    def _wait_for_key(self, target: LabeledCard | None, lines: Sequence[str]) -> int:
        """Show the live preview until the user records, skips or quits."""
        for frame in self._frames:
            key = self._show(_render_preview(frame, target, GUIDE_WAITING_BGR, lines))
            if key in (RECORD_KEY, SKIP_KEY, QUIT_KEY):
                return key
        return QUIT_KEY

    def _record_burst(self, burst: Burst, target: LabeledCard | None) -> None:
        cards = [] if target is None else [target]
        burst_frames = itertools.islice(self._frames, FRAMES_PER_POSITION * BURST_FRAME_STRIDE)
        for frame_number, frame in enumerate(burst_frames):
            self._show(_render_preview(frame, target, GUIDE_RECORDING_BGR, RECORDING_LINES))
            if frame_number % BURST_FRAME_STRIDE == 0:
                name = burst.example_names[frame_number // BURST_FRAME_STRIDE]
                self._dataset.write_example(burst.split, name, frame, cards)


def choose_guide_box(frame_width: int, frame_height: int, rng: random.Random) -> Box:
    """Pick a card-shaped outline of random size and position inside the frame."""
    height_fraction = rng.uniform(MIN_GUIDE_HEIGHT_FRACTION, MAX_GUIDE_HEIGHT_FRACTION)
    height = round(frame_height * height_fraction)
    width = round(height * CARD_WIDTH_TO_HEIGHT)
    x1 = rng.randint(0, frame_width - width)
    y1 = rng.randint(0, frame_height - height)
    return Box(x1, y1, x1 + width, y1 + height)


def _describe_burst(burst: Burst, number: int, total: int) -> tuple[str, ...]:
    how_to_record = (
        "Press SPACE to record"
        if burst.step.rank is None
        else "Fit the card to the outline, then press SPACE"
    )
    return (
        burst.step.prompt,
        how_to_record,
        f"Position {burst.position + 1} of {POSITIONS_PER_STEP}, recording {number} of {total}",
        "S: skip this step   Q: quit",
    )


def _render_preview(
    frame_bgr: np.ndarray,
    target: LabeledCard | None,
    guide_bgr: tuple[int, int, int],
    lines: Sequence[str],
) -> np.ndarray:
    """Show the frame mirrored, with the card outline on it and the instructions above it.

    The outline is drawn before mirroring so it stays on the same pixels as in the saved frame.
    """
    outlined = frame_bgr.copy()
    if target is not None:
        box = target.box
        cv2.rectangle(outlined, (box.x1, box.y1), (box.x2, box.y2), guide_bgr, GUIDE_THICKNESS)
    return add_banner(cv2.flip(outlined, FLIP_HORIZONTALLY), lines)
