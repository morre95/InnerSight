"""Recognize the cards in a frame: detect each card, then read its color."""

from typing import Protocol

import numpy as np

from innersight.cards import Box, Card, Detection
from innersight.color import classify_card_color


class CardDetector(Protocol):
    def detect(self, frame_bgr: np.ndarray) -> list[Detection]: ...


def recognize_cards(frame_bgr: np.ndarray, detector: CardDetector) -> list[Card]:
    return [
        Card(detection=detection, color=classify_card_color(_crop(frame_bgr, detection.box)))
        for detection in detector.detect(frame_bgr)
    ]


def _crop(frame_bgr: np.ndarray, box: Box) -> np.ndarray:
    return frame_bgr[box.y1 : box.y2, box.x1 : box.x2]
