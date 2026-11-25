"""Make a copy of a recorded dataset that also shows every card upside down.

Cards are recorded the right way up. A detector trained on those images alone tells a 6 from a
9 by the shape of the digit, and so reads an upside-down 9 as a 6. Train on the copy instead:
every image is in it twice, as recorded and turned half a turn.
"""

import argparse
from pathlib import Path

from innersight.capture import ALL_BURSTS
from innersight.dataset import CardDataset, turn_upside_down

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
    recorded = CardDataset(args.dataset)
    both_ways = CardDataset(args.output)
    both_ways.write_config()
    image_count = 0
    for burst in ALL_BURSTS:
        if not burst.is_recorded_in(recorded):
            continue
        for name in burst.example_names:
            frame, cards = recorded.read_example(burst.split, name)
            both_ways.write_example(burst.split, name, frame, cards)
            both_ways.write_example(
                burst.split, name + TURNED_SUFFIX, *turn_upside_down(frame, cards)
            )
            image_count += 2
    print(f"Wrote {image_count} images to {args.output}")


if __name__ == "__main__":
    main()
