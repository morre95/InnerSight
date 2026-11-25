"""Draw recognized cards onto a frame."""

import cv2
import numpy as np

from innersight.cards import Card, CardColor

OUTLINE_BGR: dict[CardColor, tuple[int, int, int]] = {
    CardColor.RED: (0, 0, 255),
    CardColor.YELLOW: (0, 255, 255),
    CardColor.GREEN: (0, 200, 0),
    CardColor.BLUE: (255, 0, 0),
    CardColor.WILD: (255, 0, 255),
    CardColor.BACK: (255, 255, 255),
    CardColor.UNKNOWN: (128, 128, 128),
}
OUTLINE_THICKNESS = 2
LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX
LABEL_SCALE = 0.6
LABEL_GAP = 8
LABEL_HEIGHT = 16


def draw_cards(frame_bgr: np.ndarray, cards: list[Card]) -> np.ndarray:
    """Return a copy of the frame with every card outlined and labeled."""
    annotated = frame_bgr.copy()
    for card in cards:
        box = card.detection.box
        outline = OUTLINE_BGR[card.color]
        label_origin = (box.x1, max(box.y1 - LABEL_GAP, LABEL_HEIGHT))
        cv2.rectangle(annotated, (box.x1, box.y1), (box.x2, box.y2), outline, OUTLINE_THICKNESS)
        cv2.putText(
            annotated, card.label, label_origin, LABEL_FONT, LABEL_SCALE, outline, OUTLINE_THICKNESS
        )
    return annotated
