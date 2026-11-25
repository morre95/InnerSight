"""Recognize the cards in a frame: detect each card, then read its color."""

from typing import Protocol

import numpy as np

from innersight.cards import BACK_RANK, WILD_RANKS, Box, Card, CardColor, Detection
from innersight.color import classify_card_color

# A card whose box is as tall or as wide as this share of the frame does not fit in the view.
FULL_VIEW_FRACTION = 0.98


class CardDetector(Protocol):
    def detect(self, frame_bgr: np.ndarray) -> list[Detection]: ...


def recognize_cards(frame_bgr: np.ndarray, detector: CardDetector) -> list[Card]:
    return [
        Card(
            detection=detection,
            color=_read_color(frame_bgr, detection),
            is_too_close=_fills_the_view(detection.box, frame_bgr),
        )
        for detection in detector.detect(frame_bgr)
    ]


def _fills_the_view(box: Box, frame_bgr: np.ndarray) -> bool:
    frame_height, frame_width = frame_bgr.shape[:2]
    return (
        box.y2 - box.y1 >= FULL_VIEW_FRACTION * frame_height
        or box.x2 - box.x1 >= FULL_VIEW_FRACTION * frame_width
    )


def _read_color(frame_bgr: np.ndarray, detection: Detection) -> CardColor:
    """Only a number or action card has a color to read from the picture.

    The back looks the same on every card, and a wild card is wild whatever colors it shows.
    """
    if detection.rank == BACK_RANK:
        return CardColor.BACK
    if detection.rank in WILD_RANKS:
        return CardColor.WILD
    return classify_card_color(crop_box(frame_bgr, detection.box))


def crop_box(frame_bgr: np.ndarray, box: Box) -> np.ndarray:
    """The part of the frame inside the box, as a view of the frame."""
    return frame_bgr[box.y1 : box.y2, box.x1 : box.x2]
