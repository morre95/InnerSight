"""Measure how well the rank of a card is read, the right way up and upside down.

It reads the validation images, whose labels tell the true rank, and reads each of them again
turned half a turn. Run it with the old and the new weights to see whether a newly trained
detector is better.

The images recorded with 'innersight capture' and the ones collected in games are counted
apart. The collected ones are cards that the weights of that time read wrongly or unsurely, so
old weights do badly on them by the way they were chosen.
"""

import argparse
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from innersight.capture import ALL_BURSTS
from innersight.dataset import VALIDATION_SPLIT, CardDataset, turn_upside_down
from innersight.detector import YoloCardDetector

DEFAULT_DATASET_DIR = Path("datasets/own-cards")
DEFAULT_WEIGHTS_FILE = Path("weights/own-cards.pt")
DEFAULT_MIN_CONFIDENCE = 0.5
NO_CARD = "no card found"
RECORDED_NAMES = frozenset(name for burst in ALL_BURSTS for name in burst.example_names)

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


def read_ranks(
    dataset: CardDataset, names: Sequence[str], detector: YoloCardDetector
) -> tuple[Readings, Readings]:
    """For every true rank, how often each rank was read: the right way up, and upside down."""
    right_way_up: Readings = {}
    upside_down: Readings = {}
    for name in names:
        frame, cards = dataset.read_example(VALIDATION_SPLIT, name)
        if not cards:
            continue
        rank = cards[0].rank
        right_way_up.setdefault(rank, Counter())[read_rank(frame, detector)] += 1
        turned_frame, _ = turn_upside_down(frame, cards)
        upside_down.setdefault(rank, Counter())[read_rank(turned_frame, detector)] += 1
    return right_way_up, upside_down


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
    dataset = CardDataset(args.dataset)
    names = dataset.example_names(VALIDATION_SPLIT)
    recorded_names = [name for name in names if name in RECORDED_NAMES]
    collected_names = [name for name in names if name not in RECORDED_NAMES]

    as_recorded, upside_down = read_ranks(dataset, recorded_names, detector)
    print_readings("As recorded", as_recorded)
    print_readings("Upside down", upside_down)
    if collected_names:
        as_collected, upside_down = read_ranks(dataset, collected_names, detector)
        print_readings("Collected in games", as_collected)
        print_readings("Collected in games, upside down", upside_down)


if __name__ == "__main__":
    main()
