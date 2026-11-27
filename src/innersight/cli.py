"""Recognize UNO cards in an image or on camera, play the guessing game, and record and review
training images."""

import argparse
import os
import random
import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

import cv2

from innersight.annotation import draw_cards
from innersight.announcement import CardAnnouncer
from innersight.capture import ALL_BURSTS, Burst, CaptureSession
from innersight.collection import (
    CollectSession,
    accept_suggestions,
    candidates_from_game,
    save_collected,
)
from innersight.dataset import CardDataset
from innersight.detector import YoloCardDetector
from innersight.errors import InboxError, InnerSightError
from innersight.game import RoundFrame, play_guessing_game
from innersight.guess_log import GuessLog
from innersight.guessing import GuessingSession
from innersight.inbox import open_inbox, pull_examples
from innersight.live_view import (
    QUIT_KEY,
    close_window,
    open_camera,
    show_frame,
    show_frame_for_key_code,
    show_frame_until_key,
    show_frame_until_key_code,
)
from innersight.recognition import CardDetector, recognize_cards
from innersight.result_board import draw_result_board
from innersight.review import ReviewSession

DEFAULT_MIN_CONFIDENCE = 0.5
DEFAULT_DATASET_DIR = Path("datasets/own-cards")
# The examples in the inbox come from the phone, whose detector is trained on this dataset.
DEFAULT_PULL_DATASET_DIR = Path("datasets/phone-cards")
DEFAULT_PULL_LIMIT = 50
PULL_TOKEN_VARIABLE = "INNERSIGHT_PULL_TOKEN"
DEFAULT_WEIGHTS_FILE = Path("weights/own-cards.pt")
DEFAULT_CARD_COUNT = 10
DEFAULT_GUESS_LOG_FILE = Path("logs/guesses.csv")


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
        case "game":
            _play_game(
                _load_detector(args),
                args.index,
                args.cards,
                args.log,
                args.speak_result,
                collect_into=args.dataset if args.collect else None,
            )
        case "capture":
            _capture_dataset(args.index, args.dataset)
        case "review":
            _review_dataset(args.index, args.dataset)
        case "pull":
            _pull_examples(args.server, args.dataset, args.limit, reviews=not args.no_review)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="innersight", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    camera_options = argparse.ArgumentParser(add_help=False)
    camera_options.add_argument(
        "--index", type=int, default=0, help="camera device (default: %(default)s)"
    )
    dataset_options = argparse.ArgumentParser(add_help=False)
    dataset_options.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help="dataset directory (default: %(default)s)",
    )
    _add_recognition_commands(commands, camera_options, dataset_options)
    _add_dataset_commands(commands, camera_options, dataset_options)
    return parser.parse_args()


def _add_recognition_commands(
    commands: "argparse._SubParsersAction[argparse.ArgumentParser]",
    camera_options: argparse.ArgumentParser,
    dataset_options: argparse.ArgumentParser,
) -> None:
    detector_options = argparse.ArgumentParser(add_help=False)
    detector_options.add_argument(
        "--weights",
        type=_existing_file,
        # A string, so that argparse checks the default with _existing_file as well.
        default=str(DEFAULT_WEIGHTS_FILE),
        help="trained detector weights (default: %(default)s)",
    )
    detector_options.add_argument(
        "--min-confidence",
        type=float,
        default=DEFAULT_MIN_CONFIDENCE,
        help="ignore detections below this confidence (default: %(default)s)",
    )

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

    game = commands.add_parser(
        "game",
        parents=[detector_options, camera_options, dataset_options],
        help="guess the cards you hold while blindfolded, and score yourself with the arrow keys",
    )
    game.add_argument(
        "--cards",
        type=_positive_int,
        default=DEFAULT_CARD_COUNT,
        help="how many cards to guess in the session (default: %(default)s)",
    )
    game.add_argument(
        "--log",
        type=Path,
        default=DEFAULT_GUESS_LOG_FILE,
        help="CSV file the rounds are added to (default: %(default)s)",
    )
    game.add_argument(
        "--speak-result",
        action="store_true",
        help="say the count of every answer when the session is finished",
    )
    game.add_argument(
        "--collect",
        action="store_true",
        help="after the session, set the true card of the rounds that were read wrongly and "
        "save them into the dataset as training examples",
    )


def _add_dataset_commands(
    commands: "argparse._SubParsersAction[argparse.ArgumentParser]",
    camera_options: argparse.ArgumentParser,
    dataset_options: argparse.ArgumentParser,
) -> None:
    commands.add_parser(
        "capture",
        parents=[camera_options, dataset_options],
        help="record training images of your own cards",
    )
    commands.add_parser(
        "review",
        parents=[camera_options, dataset_options],
        help="look through the recorded images and re-capture the bad ones",
    )
    pull = commands.add_parser(
        "pull",
        help="fetch the examples collected in the app from the inbox on your server; "
        f"the pull token is read from {PULL_TOKEN_VARIABLE}",
    )
    pull.add_argument("--server", required=True, help="address of the inbox, https://...")
    pull.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_PULL_DATASET_DIR,
        help="dataset directory (default: %(default)s)",
    )
    pull.add_argument(
        "--limit",
        type=_positive_int,
        default=DEFAULT_PULL_LIMIT,
        help="how many examples to fetch at most (default: %(default)s)",
    )
    pull.add_argument(
        "--no-review",
        action="store_true",
        help="save every example as the card set in the app, without showing it first",
    )


def _existing_file(value: str) -> Path:
    path = Path(value)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"file not found: {value}")
    return path


def _positive_int(value: str) -> int:
    if not value.isdecimal() or int(value) == 0:
        raise argparse.ArgumentTypeError(f"not a whole number above zero: {value}")
    return int(value)


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
    return CardAnnouncer(_load_voice())


def _load_voice() -> Callable[[str], None]:
    """Return the function that says a phrase aloud."""
    # Imported here because loading the audio library and the speech model is slow,
    # and not every command speaks.
    from innersight.speech import PocketTtsVoice

    return PocketTtsVoice().say


def _stay_silent(phrase: str) -> None:
    """Stand in for a voice when speech is muted."""


def _recognize_camera(detector: CardDetector, camera_index: int, announcer: CardAnnouncer) -> None:
    with open_camera(camera_index) as frames:
        for frame in frames:
            cards = recognize_cards(frame, detector)
            announcer.observe(cards)
            if show_frame(draw_cards(frame, cards)) == QUIT_KEY:
                break


def _play_game(
    detector: CardDetector,
    camera_index: int,
    card_count: int,
    log_file: Path,
    speaks_result: bool,
    collect_into: Path | None,
) -> None:
    """Play a session and show its result. With a dataset to collect into, the rounds are
    then gone through once more, to save the misread ones as training examples."""
    session = GuessingSession(card_count, _load_voice(), speaks_result=speaks_result)
    started_at = datetime.now()
    guess_log = GuessLog(log_file, started_at)
    with open_camera(camera_index) as frames:
        round_frames = play_guessing_game(
            frames, show_frame_for_key_code, detector, session, guess_log
        )
    if not session.rounds:
        return
    print(f"The rounds are logged in {log_file}")
    try:
        pictures = [round_frame.picture for round_frame in round_frames]
        show_frame_until_key(draw_result_board(session.rounds, pictures))
        if collect_into is not None:
            _collect_examples(round_frames, started_at, collect_into)
    finally:
        close_window()


def _collect_examples(
    round_frames: Sequence[RoundFrame], started_at: datetime, dataset_dir: Path
) -> None:
    candidates = candidates_from_game(round_frames, started_at)
    examples = CollectSession(show_frame_until_key_code).run(candidates).saved
    if examples:
        save_collected(CardDataset(dataset_dir), examples)
    print(f"Saved {len(examples)} of {len(candidates)} cards as examples in {dataset_dir}")


def _capture_dataset(camera_index: int, dataset_dir: Path) -> None:
    dataset = CardDataset(dataset_dir)
    missing_bursts = [burst for burst in ALL_BURSTS if not burst.is_recorded_in(dataset)]
    if not missing_bursts:
        print(f"Everything is recorded in {dataset_dir}. Use 'innersight review' to redo images.")
        return
    _record_bursts(camera_index, dataset, missing_bursts)
    print(f"Recorded images are in {dataset_dir}. Run this again to record what is missing.")


def _review_dataset(camera_index: int, dataset_dir: Path) -> None:
    dataset = CardDataset(dataset_dir)
    recorded_bursts = [burst for burst in ALL_BURSTS if burst.is_recorded_in(dataset)]
    if not recorded_bursts:
        sys.exit(f"No recorded images found in {dataset_dir}")
    try:
        rejected_bursts = ReviewSession(show_frame_until_key, dataset).run(recorded_bursts)
    finally:
        close_window()
    if not rejected_bursts:
        print("Nothing was marked for re-capture.")
        return
    print(f"Re-capturing {len(rejected_bursts)} of {len(recorded_bursts)} recorded positions.")
    _record_bursts(camera_index, dataset, rejected_bursts)


def _record_bursts(camera_index: int, dataset: CardDataset, bursts: Sequence[Burst]) -> None:
    say = _load_voice()
    with open_camera(camera_index) as frames:
        CaptureSession(frames, show_frame, dataset, random.Random(), say).record(bursts)


def _pull_examples(server_url: str, dataset_dir: Path, limit: int, reviews: bool) -> None:
    token = os.environ.get(PULL_TOKEN_VARIABLE)
    if not token:
        raise InboxError(f"Set {PULL_TOKEN_VARIABLE} to the pull token of the inbox")
    review = CollectSession(show_frame_until_key_code).run if reviews else accept_suggestions
    try:
        report = pull_examples(
            open_inbox(server_url, token), CardDataset(dataset_dir), review, limit
        )
    finally:
        close_window()
    print(f"Examples saved in {dataset_dir}: {report.saved_count}")
    print(f"Examples discarded: {report.discarded_count}")
    if report.undecided_count:
        print(f"{report.undecided_count} were not decided on and are still in the inbox.")
    if report.unusable_ids:
        print(f"These cannot be used and are still in the inbox: {', '.join(report.unusable_ids)}")
