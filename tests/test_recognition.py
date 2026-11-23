import numpy as np

from innersight.cards import Box, Card, CardColor, Detection
from innersight.recognition import recognize_cards

FRAME_HEIGHT = 200
FRAME_WIDTH = 400
PURE_RED_BGR = (0, 0, 220)
PURE_BLUE_BGR = (220, 0, 0)


class FakeDetector:
    def __init__(self, detections: list[Detection]) -> None:
        self._detections = detections

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        return self._detections


def make_frame_with_red_left_half_and_blue_right_half() -> np.ndarray:
    frame = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    frame[:, : FRAME_WIDTH // 2] = PURE_RED_BGR
    frame[:, FRAME_WIDTH // 2 :] = PURE_BLUE_BGR
    return frame


def test_gives_each_detection_the_color_inside_its_box() -> None:
    frame = make_frame_with_red_left_half_and_blue_right_half()
    left = Detection(rank="7", confidence=0.9, box=Box(0, 0, 200, 200))
    right = Detection(rank="skip", confidence=0.8, box=Box(200, 0, 400, 200))

    cards = recognize_cards(frame, FakeDetector([left, right]))

    assert cards == [Card(left, CardColor.RED), Card(right, CardColor.BLUE)]


def test_returns_no_cards_when_nothing_is_detected() -> None:
    frame = make_frame_with_red_left_half_and_blue_right_half()

    assert recognize_cards(frame, FakeDetector([])) == []
