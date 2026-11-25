"""Measure how well the rank of a card is read, the right way up and upside down.

It reads the validation images recorded with 'innersight capture', whose labels tell the true
rank, and reads each of them again turned half a turn. Run it with the old and the new weights
to see whether a newly trained detector is better.
"""

import argparse
from collections import Counter
from pathlib import Path

import numpy as np

from innersight.capture import ALL_BURSTS
from innersight.dataset import VALIDATION_SPLIT, CardDataset, turn_upside_down
from innersight.detector import YoloCardDetector

DEFAULT_DATASET_DIR = Path("datasets/own-cards")
DEFAULT_WEIGHTS_FILE = Path("weights/own-cards.pt")
DEFAULT_MIN_CONFIDENCE = 0.5
NO_CARD = "no card found"

Readings = dict[str, Counter[str]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS_FILE)
    parser.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)
    return parser.parse_args()


def read_rank(frame_bgr: np.ndarray, detector: YoloCardDetector) -> str:
    surest = max(detector.detect(frame_bgr), key=lambda found: found.confidence, default=None)
    return NO_CARD if surest is None else surest.rank


def read_ranks(dataset: CardDataset, detector: YoloCardDetector) -> tuple[Readings, Readings]:
    """For every true rank, how often each rank was read: as recorded, and upside down."""
    as_recorded: Readings = {}
    upside_down: Readings = {}
    for burst in ALL_BURSTS:
        if burst.split != VALIDATION_SPLIT or not burst.is_recorded_in(dataset):
            continue
        for name in burst.example_names:
            frame, cards = dataset.read_example(burst.split, name)
            if not cards:
                continue
            rank = cards[0].rank
            as_recorded.setdefault(rank, Counter())[read_rank(frame, detector)] += 1
            turned_frame, _ = turn_upside_down(frame, cards)
            upside_down.setdefault(rank, Counter())[read_rank(turned_frame, detector)] += 1
    return as_recorded, upside_down


def print_readings(title: str, readings: Readings) -> None:
    image_count = sum(counts.total() for counts in readings.values())
    right_count = sum(counts[rank] for rank, counts in readings.items())
    print(f"{title}: {right_count} of {image_count} ranks read right")
    for rank, counts in readings.items():
        other_readings = ", ".join(
            f"{reading} {count}" for reading, count in counts.most_common() if reading != rank
        )
        print(f"  {rank:<13}{counts[rank]:>3} of {counts.total():<3} {other_readings}")


def main() -> None:
    args = parse_args()
    detector = YoloCardDetector(args.weights, args.min_confidence)
    as_recorded, upside_down = read_ranks(CardDataset(args.dataset), detector)
    print_readings("As recorded", as_recorded)
    print_readings("Upside down", upside_down)


if __name__ == "__main__":
    main()
