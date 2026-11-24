"""Recognize the cards in a frame: detect each card, then read its color."""

from typing import Protocol

import numpy as np

from innersight.cards import BACK_RANK, WILD_RANKS, Box, Card, CardColor, Detection
from innersight.color import classify_card_color


class CardDetector(Protocol):
    def detect(self, frame_bgr: np.ndarray) -> list[Detection]: ...


def recognize_cards(frame_bgr: np.ndarray, detector: CardDetector) -> list[Card]:
    return [
        Card(detection=detection, color=_read_color(frame_bgr, detection))
        for detection in detector.detect(frame_bgr)
    ]


def _read_color(frame_bgr: np.ndarray, detection: Detection) -> CardColor:
    """Only a number or action card has a color to read from the picture.

    The back looks the same on every card, and a wild card is wild whatever colors it shows.
    """
    if detection.rank == BACK_RANK:
        return CardColor.BACK
    if detection.rank in WILD_RANKS:
        return CardColor.WILD
    return classify_card_color(_crop(frame_bgr, detection.box))


def _crop(frame_bgr: np.ndarray, box: Box) -> np.ndarray:
    return frame_bgr[box.y1 : box.y2, box.x1 : box.x2]
