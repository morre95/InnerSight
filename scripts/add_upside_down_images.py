"""Make a copy of a dataset that also shows every card upside down.

Cards are recorded the right way up. A detector trained on those images alone tells a 6 from a
9 by the shape of the digit, and so reads an upside-down 9 as a 6. Train on the copy instead:
every image is in it twice, as it is and turned half a turn. That goes for the images
collected in games as well as for the recorded ones.
"""

import argparse
from pathlib import Path

from innersight.dataset import TRAIN_SPLIT, VALIDATION_SPLIT, CardDataset, turn_upside_down

DEFAULT_DATASET_DIR = Path("datasets/own-cards")
DEFAULT_OUTPUT_DIR = Path("datasets/own-cards-both-ways")
TURNED_SUFFIX = "_turned"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    original = CardDataset(args.dataset)
    both_ways = CardDataset(args.output)
    both_ways.write_config()
    image_count = 0
    for split in (TRAIN_SPLIT, VALIDATION_SPLIT):
        for name in original.example_names(split):
            frame, cards = original.read_example(split, name)
            both_ways.write_example(split, name, frame, cards)
            both_ways.write_example(split, name + TURNED_SUFFIX, *turn_upside_down(frame, cards))
            image_count += 2
    print(f"Wrote {image_count} images to {args.output}")


if __name__ == "__main__":
    main()
