"""Classify the color of a UNO card from a cropped image of it."""

import cv2
import numpy as np

from innersight.cards import CardColor

# OpenCV hue runs from 0 to 179. Ranges are half-open [start, end), and red wraps around zero.
# These are starting values: calibrate them against your own deck, camera and lighting.
HUE_RANGES: dict[CardColor, tuple[tuple[int, int], ...]] = {
    CardColor.RED: ((0, 12), (160, 180)),
    CardColor.YELLOW: ((12, 40),),
    CardColor.GREEN: ((40, 90),),
    CardColor.BLUE: ((90, 140),),
}

# A pixel counts as colored when it is neither washed out (white, glare) nor dark (black).
MIN_SATURATION = 70
MIN_VALUE = 50

# Only the middle of the crop is analyzed, because the edges of a detection box
# show the table around a rotated card.
CENTER_FRACTION = 0.6

# Below this share of colored pixels the card has no color of its own.
MIN_COLORED_FRACTION = 0.05

# A number or action card is one color. Background or glare splits the colored pixels.
MIN_DOMINANT_SHARE = 0.6


def classify_card_color(card_bgr: np.ndarray) -> CardColor:
    """Return the color of a number or action card, or UNKNOWN when no single color dominates.

    That happens when the card is too far away, in poor light, or in glare.
    """
    hsv = cv2.cvtColor(_crop_center(card_bgr), cv2.COLOR_BGR2HSV)
    hue, saturation, value = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    colored_hues = hue[(saturation >= MIN_SATURATION) & (value >= MIN_VALUE)]
    if colored_hues.size < MIN_COLORED_FRACTION * hue.size:
        return CardColor.UNKNOWN

    pixel_counts = {
        color: _count_hues_in_ranges(colored_hues, ranges) for color, ranges in HUE_RANGES.items()
    }
    dominant_color = max(pixel_counts, key=pixel_counts.__getitem__)
    if pixel_counts[dominant_color] < MIN_DOMINANT_SHARE * colored_hues.size:
        return CardColor.UNKNOWN
    return dominant_color


def _crop_center(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    margin_y = round(height * (1 - CENTER_FRACTION) / 2)
    margin_x = round(width * (1 - CENTER_FRACTION) / 2)
    return image[margin_y : height - margin_y, margin_x : width - margin_x]


def _count_hues_in_ranges(hues: np.ndarray, ranges: tuple[tuple[int, int], ...]) -> int:
    return sum(int(np.count_nonzero((hues >= start) & (hues < end))) for start, end in ranges)
