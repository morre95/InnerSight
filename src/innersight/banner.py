"""Put lines of text in a banner above an image."""

from collections.abc import Sequence

import cv2
import numpy as np

TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX
TEXT_SCALE = 0.6
TEXT_MARGIN = 10
TEXT_LINE_HEIGHT = 26
TEXT_BGR = (255, 255, 255)
TEXT_THICKNESS = 1
# Every banner has room for this many lines, so a window keeps its size when the text changes.
BANNER_LINE_COUNT = 4
BANNER_HEIGHT = TEXT_LINE_HEIGHT * BANNER_LINE_COUNT + TEXT_MARGIN


def add_banner(image_bgr: np.ndarray, lines: Sequence[str]) -> np.ndarray:
    """Return the image with a black banner above it that holds the lines of text."""
    banner = np.zeros((BANNER_HEIGHT, image_bgr.shape[1], 3), dtype=np.uint8)
    for line_number, line in enumerate(lines, start=1):
        origin = (TEXT_MARGIN, TEXT_LINE_HEIGHT * line_number)
        cv2.putText(banner, line, origin, TEXT_FONT, TEXT_SCALE, TEXT_BGR, TEXT_THICKNESS)
    return np.vstack([banner, image_bgr])
