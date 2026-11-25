"""Classify the color of a UNO card from a cropped image of it."""

import cv2
import numpy as np

from innersight.cards import CardColor

HueRange = tuple[int, int]

# OpenCV hue runs from 0 to 179. Ranges are half-open [start, end), and red wraps around zero.
# The values in this file are tuned with scripts/measure_color_reading.py on cards recorded with
# one webcam, in a room lit mostly by a monitor. Tune them again for another camera or light.
# Red reaches far down into purple, as the bluish light of a monitor turns a red card purple.
RED_HUES: tuple[HueRange, ...] = ((0, 12), (130, 180))
YELLOW_HUES: tuple[HueRange, ...] = ((12, 34),)
GREEN_HUES: tuple[HueRange, ...] = ((46, 90),)
BLUE_HUES: tuple[HueRange, ...] = ((90, 130),)

# A webcam shows a yellow card and a green card in nearly the same olive hue. In these hues the
# brightness tells them apart: next to the white of the card, yellow is bright and green dark.
YELLOW_OR_GREEN_HUES: tuple[HueRange, ...] = ((34, 46),)
MIN_YELLOW_VALUE = 160

# A pixel counts as colored when it is neither washed out (white, glare) nor dark (black).
MIN_SATURATION = 90
MIN_VALUE = 50

# The blue of a card is strong. White in the bluish light of a monitor is a weak blue, and
# would otherwise outnumber the color of a red or yellow card.
MIN_BLUE_SATURATION = 160

# The white of the card is taken from the brightest pixels: in each color channel, the level
# that this share of the crop stays below.
WHITE_PERCENTILE = 90

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
    hsv = cv2.cvtColor(_crop_center(_balance_white(card_bgr)), cv2.COLOR_BGR2HSV)
    hue, saturation, value = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    is_colored = (saturation >= MIN_SATURATION) & (value >= MIN_VALUE)
    is_yellow_or_green = _is_in_ranges(hue, YELLOW_OR_GREEN_HUES)
    is_bright = value >= MIN_YELLOW_VALUE
    is_color = {
        CardColor.RED: _is_in_ranges(hue, RED_HUES),
        CardColor.YELLOW: _is_in_ranges(hue, YELLOW_HUES) | (is_yellow_or_green & is_bright),
        CardColor.GREEN: _is_in_ranges(hue, GREEN_HUES) | (is_yellow_or_green & ~is_bright),
        CardColor.BLUE: _is_in_ranges(hue, BLUE_HUES) & (saturation >= MIN_BLUE_SATURATION),
    }
    pixel_counts = {
        color: int(np.count_nonzero(is_colored & mask)) for color, mask in is_color.items()
    }
    colored_count = sum(pixel_counts.values())
    if colored_count < MIN_COLORED_FRACTION * hue.size:
        return CardColor.UNKNOWN

    dominant_color = max(pixel_counts, key=pixel_counts.__getitem__)
    if pixel_counts[dominant_color] < MIN_DOMINANT_SHARE * colored_count:
        return CardColor.UNKNOWN
    return dominant_color


def _balance_white(image_bgr: np.ndarray) -> np.ndarray:
    """Remove the tint of the light, so that the white of the card becomes white.

    A card has a white border and a white digit. Scaling every color channel so that its
    brightest pixels reach the same level takes away the tint that the light gives them,
    and with it the tint it gives the color of the card.
    """
    white = np.percentile(image_bgr.reshape(-1, 3), WHITE_PERCENTILE, axis=0)
    gains = white.max() / np.maximum(white, 1)
    return np.clip(image_bgr * gains, 0, 255).astype(np.uint8)


def _crop_center(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    margin_y = round(height * (1 - CENTER_FRACTION) / 2)
    margin_x = round(width * (1 - CENTER_FRACTION) / 2)
    return image[margin_y : height - margin_y, margin_x : width - margin_x]


def _is_in_ranges(hues: np.ndarray, ranges: tuple[HueRange, ...]) -> np.ndarray:
    """Which of the hues are inside any of the ranges."""
    is_inside = np.zeros(hues.shape, dtype=bool)
    for start, end in ranges:
        is_inside |= (hues >= start) & (hues < end)
    return is_inside
