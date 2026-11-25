import numpy as np

from innersight.cards import CARD_BACK, Box, Card, CardColor, Detection
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
    left = Detection(rank="7", confidence=0.9, box=Box(0, 20, 200, 180))
    right = Detection(rank="skip", confidence=0.8, box=Box(200, 20, 400, 180))

    cards = recognize_cards(frame, FakeDetector([left, right]))

    assert cards == [Card(left, CardColor.RED), Card(right, CardColor.BLUE)]


def test_gives_the_back_no_color_of_its_own_even_when_its_box_is_red() -> None:
    frame = make_frame_with_red_left_half_and_blue_right_half()
    back = Detection(rank="back", confidence=0.9, box=Box(0, 20, 200, 180))

    cards = recognize_cards(frame, FakeDetector([back]))

    assert [card.face for card in cards] == [CARD_BACK]


def test_calls_a_wild_card_wild_even_when_its_box_is_red() -> None:
    frame = make_frame_with_red_left_half_and_blue_right_half()
    joker = Detection(rank="joker", confidence=0.9, box=Box(0, 20, 200, 180))

    cards = recognize_cards(frame, FakeDetector([joker]))

    assert cards == [Card(joker, CardColor.WILD)]


def test_returns_no_cards_when_nothing_is_detected() -> None:
    frame = make_frame_with_red_left_half_and_blue_right_half()

    assert recognize_cards(frame, FakeDetector([])) == []


def test_finds_a_card_too_close_when_it_is_as_tall_as_the_frame() -> None:
    frame = make_frame_with_red_left_half_and_blue_right_half()
    as_tall_as_the_frame = Detection(rank="7", confidence=0.9, box=Box(0, 0, 150, FRAME_HEIGHT))

    (card,) = recognize_cards(frame, FakeDetector([as_tall_as_the_frame]))

    assert card.is_too_close


def test_finds_a_card_too_close_when_it_is_as_wide_as_the_frame() -> None:
    frame = make_frame_with_red_left_half_and_blue_right_half()
    as_wide_as_the_frame = Detection(rank="7", confidence=0.9, box=Box(0, 50, FRAME_WIDTH, 150))

    (card,) = recognize_cards(frame, FakeDetector([as_wide_as_the_frame]))

    assert card.is_too_close


def test_does_not_find_a_card_too_close_when_it_fits_in_the_frame() -> None:
    frame = make_frame_with_red_left_half_and_blue_right_half()
    with_room_to_spare = Detection(rank="7", confidence=0.9, box=Box(10, 10, 130, 190))

    (card,) = recognize_cards(frame, FakeDetector([with_room_to_spare]))

    assert not card.is_too_close
