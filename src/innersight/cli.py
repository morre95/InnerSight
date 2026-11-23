"""Recognize UNO cards in an image or live on camera, say them aloud, and record training images."""

import argparse
import random
import sys
from pathlib import Path

import cv2

from innersight.annotation import draw_cards
from innersight.announcement import CardAnnouncer
from innersight.capture import CaptureSession
from innersight.dataset import CardDataset
from innersight.detector import YoloCardDetector
from innersight.errors import InnerSightError
from innersight.live_view import QUIT_KEY, open_camera, show_frame
from innersight.recognition import CardDetector, recognize_cards

DEFAULT_MIN_CONFIDENCE = 0.5
DEFAULT_DATASET_DIR = Path("datasets/own-cards")


def main() -> None:
    args = _parse_args()
    try:
        _run_command(args)
    except InnerSightError as error:
        sys.exit(str(error))


def _run_command(args: argparse.Namespace) -> None:
    match args.command:
        case "image":
            _recognize_image(_load_detector(args), args.path, args.output)
        case "camera":
            _recognize_camera(_load_detector(args), args.index, _create_announcer(args.mute))
        case "capture":
            _capture_dataset(args.index, args.dataset)


def _parse_args() -> argparse.Namespace:
    detector_options = argparse.ArgumentParser(add_help=False)
    detector_options.add_argument(
        "--weights", type=_existing_file, required=True, help="trained detector weights (.pt)"
    )
    detector_options.add_argument(
        "--min-confidence",
        type=float,
        default=DEFAULT_MIN_CONFIDENCE,
        help="ignore detections below this confidence (default: %(default)s)",
    )
    camera_options = argparse.ArgumentParser(add_help=False)
    camera_options.add_argument(
        "--index", type=int, default=0, help="camera device (default: %(default)s)"
    )

    parser = argparse.ArgumentParser(prog="innersight", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    image = commands.add_parser(
        "image", parents=[detector_options], help="recognize the cards in one image"
    )
    image.add_argument("path", type=_existing_file, help="image to read")
    image.add_argument("--output", type=_image_output_path, help="write the annotated image here")

    camera = commands.add_parser(
        "camera",
        parents=[detector_options, camera_options],
        help="recognize cards live and say them aloud; press q to quit",
    )
    camera.add_argument("--mute", action="store_true", help="do not say the cards aloud")

    capture = commands.add_parser(
        "capture", parents=[camera_options], help="record training images of your own cards"
    )
    capture.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help="dataset directory to fill (default: %(default)s)",
    )

    return parser.parse_args()


def _existing_file(value: str) -> Path:
    path = Path(value)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"file not found: {value}")
    return path


def _image_output_path(value: str) -> Path:
    if not cv2.haveImageWriter(value):
        raise argparse.ArgumentTypeError(f"unsupported image format: {value}")
    return Path(value)


def _load_detector(args: argparse.Namespace) -> YoloCardDetector:
    return YoloCardDetector(args.weights, args.min_confidence)


def _recognize_image(detector: CardDetector, image_path: Path, output_path: Path | None) -> None:
    frame = cv2.imread(str(image_path))
    if frame is None:
        sys.exit(f"Could not read an image from {image_path}")

    cards = recognize_cards(frame, detector)
    for card in cards:
        print(f"{card.label} ({card.detection.confidence:.2f})")

    if output_path is not None and not cv2.imwrite(str(output_path), draw_cards(frame, cards)):
        sys.exit(f"Could not write the annotated image to {output_path}")


def _create_announcer(is_muted: bool) -> CardAnnouncer:
    if is_muted:
        return CardAnnouncer(_stay_silent)
    # Imported here because loading the audio library and the speech model is slow,
    # and the other commands never speak.
    from innersight.speech import PocketTtsVoice

    return CardAnnouncer(PocketTtsVoice().say)


def _stay_silent(phrase: str) -> None:
    """Stand in for a voice when speech is muted."""


def _recognize_camera(detector: CardDetector, camera_index: int, announcer: CardAnnouncer) -> None:
    with open_camera(camera_index) as frames:
        for frame in frames:
            cards = recognize_cards(frame, detector)
            announcer.observe(cards)
            if show_frame(draw_cards(frame, cards)) == QUIT_KEY:
                break


def _capture_dataset(camera_index: int, dataset_dir: Path) -> None:
    with open_camera(camera_index) as frames:
        CaptureSession(frames, show_frame, CardDataset(dataset_dir), random.Random()).run()
    print(f"Recorded images are in {dataset_dir}. Run this again to record what is missing.")
