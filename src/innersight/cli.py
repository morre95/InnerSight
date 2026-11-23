"""Recognize UNO cards in an image or in a live camera feed."""

import argparse
import sys
from pathlib import Path

import cv2

from innersight.annotation import draw_cards
from innersight.detector import YoloCardDetector
from innersight.recognition import CardDetector, recognize_cards

WINDOW_TITLE = "InnerSight"
QUIT_KEY = ord("q")
DEFAULT_MIN_CONFIDENCE = 0.5


def main() -> None:
    args = _parse_args()
    detector = YoloCardDetector(args.weights, args.min_confidence)
    if args.command == "image":
        _recognize_image(detector, args.path, args.output)
    else:
        _recognize_camera(detector, args.index)


def _parse_args() -> argparse.Namespace:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--weights", type=_existing_file, required=True, help="trained detector weights (.pt)"
    )
    shared.add_argument(
        "--min-confidence",
        type=float,
        default=DEFAULT_MIN_CONFIDENCE,
        help="ignore detections below this confidence (default: %(default)s)",
    )

    parser = argparse.ArgumentParser(prog="innersight", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    image = commands.add_parser("image", parents=[shared], help="recognize the cards in one image")
    image.add_argument("path", type=_existing_file, help="image to read")
    image.add_argument("--output", type=_image_output_path, help="write the annotated image here")

    camera = commands.add_parser(
        "camera", parents=[shared], help="recognize cards live; press q to quit"
    )
    camera.add_argument("--index", type=int, default=0, help="camera device (default: %(default)s)")

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


def _recognize_image(detector: CardDetector, image_path: Path, output_path: Path | None) -> None:
    frame = cv2.imread(str(image_path))
    if frame is None:
        sys.exit(f"Could not read an image from {image_path}")

    cards = recognize_cards(frame, detector)
    for card in cards:
        print(f"{card.label} ({card.detection.confidence:.2f})")

    if output_path is not None and not cv2.imwrite(str(output_path), draw_cards(frame, cards)):
        sys.exit(f"Could not write the annotated image to {output_path}")


def _recognize_camera(detector: CardDetector, camera_index: int) -> None:
    capture = cv2.VideoCapture(camera_index)
    if not capture.isOpened():
        sys.exit(f"Could not open camera {camera_index}")

    try:
        while True:
            is_frame_read, frame = capture.read()
            if not is_frame_read:
                sys.exit(f"Camera {camera_index} stopped delivering frames")
            cv2.imshow(WINDOW_TITLE, draw_cards(frame, recognize_cards(frame, detector)))
            if cv2.waitKey(1) & 0xFF == QUIT_KEY:
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()
