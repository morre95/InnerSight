"""Measure how well the color of a card is read, on the images recorded with 'innersight capture'.

The file name of a recorded image tells the true color of its card. Run this before and after
changing the values in src/innersight/color.py, to see whether the change helps.
"""

import argparse
from collections import Counter
from pathlib import Path

import cv2

from innersight.cards import SUIT_COLORS, CardColor
from innersight.dataset import TRAIN_SPLIT, VALIDATION_SPLIT
from innersight.detector import YoloCardDetector
from innersight.recognition import recognize_cards

DEFAULT_DATASET_DIR = Path("datasets/own-cards")
DEFAULT_WEIGHTS_FILE = Path("weights/own-cards.pt")
DEFAULT_MIN_CONFIDENCE = 0.5
NO_CARD = "no card found"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS_FILE)
    parser.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)
    return parser.parse_args()


def read_colors(image_dir: Path, detector: YoloCardDetector) -> dict[CardColor, Counter[str]]:
    """For every true color, how often each color was read in the images of the directory."""
    readings: dict[CardColor, Counter[str]] = {color: Counter() for color in SUIT_COLORS}
    for image_file in sorted(image_dir.glob("*.jpg")):
        # A recorded image is named <color>_<rank>_p<position>_f<frame>.
        color_name = image_file.stem.split("_")[0]
        if color_name not in SUIT_COLORS:
            continue
        cards = recognize_cards(cv2.imread(str(image_file)), detector)
        surest_card = max(cards, key=lambda card: card.detection.confidence, default=None)
        reading = NO_CARD if surest_card is None else str(surest_card.color)
        readings[CardColor(color_name)][reading] += 1
    return readings


def print_readings(split: str, readings: dict[CardColor, Counter[str]]) -> None:
    image_count = sum(counts.total() for counts in readings.values())
    right_count = sum(counts[color] for color, counts in readings.items())
    print(f"{split}: {right_count} of {image_count} colors read right")
    for color, counts in readings.items():
        other_readings = ", ".join(
            f"{reading} {count}" for reading, count in counts.most_common() if reading != color
        )
        print(f"  {color:<7}{counts[color]:>4} of {counts.total():<4} {other_readings}")


def main() -> None:
    args = parse_args()
    detector = YoloCardDetector(args.weights, args.min_confidence)
    for split in (TRAIN_SPLIT, VALIDATION_SPLIT):
        print_readings(split, read_colors(args.dataset / split / "images", detector))


if __name__ == "__main__":
    main()
