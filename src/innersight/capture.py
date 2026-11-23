"""Record a labeled training dataset by holding up cards to the camera, one at a time."""

import itertools
import random
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from innersight.cards import DECK, Box
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
TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX
TEXT_SCALE = 0.6
TEXT_MARGIN = 10
TEXT_LINE_HEIGHT = 26
TEXT_BGR = (255, 255, 255)
TEXT_THICKNESS = 1
# The instructions sit in a banner above the camera image, tall enough for the longest of them.
BANNER_LINE_COUNT = 4
BANNER_HEIGHT = TEXT_LINE_HEIGHT * BANNER_LINE_COUNT + TEXT_MARGIN
RECORDING_LINES = ("Recording...",)


@dataclass(frozen=True)
class CaptureStep:
    """One thing to show the camera: a card, or no card at all when the rank is None."""

    name: str
    prompt: str
    rank: str | None


CAPTURE_STEPS: tuple[CaptureStep, ...] = (
    *(
        CaptureStep(
            name=f"{face.color}_{face.rank}", prompt=f"Hold up: {face.label}", rank=face.rank
        )
        for face in DECK
    ),
    CaptureStep(
        name="background", prompt="Show no card: only you, your hands, the room", rank=None
    ),
)


class CaptureSession:
    """Walks the user through every capture step the dataset does not hold yet."""

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

    def run(self) -> None:
        self._dataset.write_config()
        pending_steps = [step for step in CAPTURE_STEPS if not self._is_recorded(step)]
        frame_height, frame_width = next(self._frames).shape[:2]
        for step in pending_steps:
            for position in range(POSITIONS_PER_STEP):
                target = self._choose_target(step, frame_width, frame_height)
                key = self._wait_for_key(target, _describe_step(step, position))
                if key == QUIT_KEY:
                    return
                if key == SKIP_KEY:
                    break
                self._record_burst(step, position, target)

    def _is_recorded(self, step: CaptureStep) -> bool:
        return all(
            self._dataset.has_example(_split_for(position), _example_name(step, position, frame))
            for position in range(POSITIONS_PER_STEP)
            for frame in range(FRAMES_PER_POSITION)
        )

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

    def _record_burst(self, step: CaptureStep, position: int, target: LabeledCard | None) -> None:
        cards = [] if target is None else [target]
        burst_frames = itertools.islice(self._frames, FRAMES_PER_POSITION * BURST_FRAME_STRIDE)
        for frame_number, frame in enumerate(burst_frames):
            self._show(_render_preview(frame, target, GUIDE_RECORDING_BGR, RECORDING_LINES))
            if frame_number % BURST_FRAME_STRIDE == 0:
                name = _example_name(step, position, frame_number // BURST_FRAME_STRIDE)
                self._dataset.write_example(_split_for(position), name, frame, cards)


def choose_guide_box(frame_width: int, frame_height: int, rng: random.Random) -> Box:
    """Pick a card-shaped outline of random size and position inside the frame."""
    height_fraction = rng.uniform(MIN_GUIDE_HEIGHT_FRACTION, MAX_GUIDE_HEIGHT_FRACTION)
    height = round(frame_height * height_fraction)
    width = round(height * CARD_WIDTH_TO_HEIGHT)
    x1 = rng.randint(0, frame_width - width)
    y1 = rng.randint(0, frame_height - height)
    return Box(x1, y1, x1 + width, y1 + height)


def _split_for(position: int) -> str:
    """The last position of every step is held back for validation.

    Splitting by position keeps the near-identical frames of one burst in the same split.
    """
    return VALIDATION_SPLIT if position == POSITIONS_PER_STEP - 1 else TRAIN_SPLIT


def _example_name(step: CaptureStep, position: int, frame: int) -> str:
    return f"{step.name}_p{position}_f{frame}"


def _describe_step(step: CaptureStep, position: int) -> tuple[str, ...]:
    how_to_record = (
        "Press SPACE to record"
        if step.rank is None
        else "Fit the card to the outline, then press SPACE"
    )
    step_number = CAPTURE_STEPS.index(step) + 1
    return (
        step.prompt,
        how_to_record,
        f"Step {step_number}/{len(CAPTURE_STEPS)}, position {position + 1}/{POSITIONS_PER_STEP}",
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
    mirrored = cv2.flip(outlined, FLIP_HORIZONTALLY)

    banner = np.zeros((BANNER_HEIGHT, frame_bgr.shape[1], 3), dtype=np.uint8)
    for line_number, line in enumerate(lines, start=1):
        origin = (TEXT_MARGIN, TEXT_LINE_HEIGHT * line_number)
        cv2.putText(banner, line, origin, TEXT_FONT, TEXT_SCALE, TEXT_BGR, TEXT_THICKNESS)
    return np.vstack([banner, mirrored])
