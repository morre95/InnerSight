"""Stand-ins for the camera and the preview window, shared by the capture and review tests."""

import itertools
import random
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np

from innersight.capture import RECORD_KEY, Burst, CaptureSession
from innersight.dataset import CardDataset
from innersight.inbox import InboxExample

FRAME_HEIGHT = 48
FRAME_WIDTH = 64
BLACK_FRAME = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)


class ScriptedWindow:
    """Stands in for the preview window: presses the scripted keys, then repeats the last one."""

    def __init__(self, *keys: int) -> None:
        self._keys = list(keys)
        self.frames_shown = 0
        self.last_frame: np.ndarray | None = None

    def __call__(self, frame_bgr: np.ndarray) -> int:
        self.frames_shown += 1
        self.last_frame = frame_bgr
        return self._keys.pop(0) if len(self._keys) > 1 else self._keys[0]


def stay_silent(phrase: str) -> None:
    """Stands in for the voice in the tests that do not look at what is said."""


def record_bursts(
    dataset_dir: Path,
    bursts: Sequence[Burst],
    window: ScriptedWindow | None = None,
    camera_frame: np.ndarray = BLACK_FRAME,
    say: Callable[[str], None] = stay_silent,
) -> None:
    """Run a capture session on a camera that always delivers the same frame.

    Without a scripted window, the record key is pressed for every burst.
    """
    CaptureSession(
        itertools.repeat(camera_frame),
        window or ScriptedWindow(RECORD_KEY),
        CardDataset(dataset_dir),
        random.Random(0),
        say,
    ).record(bursts)


class FakeInbox:
    """Stands in for the inbox on the server: holds examples with their pictures in memory."""

    def __init__(self, examples: Sequence[InboxExample], image: bytes) -> None:
        self._examples = list(examples)
        self._image = image

    @property
    def ids(self) -> list[str]:
        return [example.id for example in self._examples]

    def list_examples(self, limit: int) -> list[InboxExample]:
        return self._examples[:limit]

    def fetch_image(self, example_id: str) -> bytes:
        return self._image

    def delete(self, example_id: str) -> None:
        self._examples = [example for example in self._examples if example.id != example_id]
