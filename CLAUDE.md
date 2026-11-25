# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

InnerSight recognizes the UNO card held up to a camera and says it aloud. There are two
implementations of the same pipeline that must be kept in step:

- `src/innersight/` — Python CLI for a desktop webcam (OpenCV window, Ultralytics YOLO, Pocket TTS).
- `mobile/` — Flutter Android app (ONNX Runtime, `flutter_tts`). It is a port of the Python
  logic; several Dart classes are documented as a "direct port" of a named Python class.

## Commands

Python (run from the repository root, managed with `uv`):

```bash
uv sync
uv run pytest                                   # all tests
uv run pytest tests/test_guessing.py            # one file
uv run pytest tests/test_guessing.py::test_says_which_answer_was_given   # one test
uv run ruff check
uv run ruff format --check
```

Running the app (needs `weights/own-cards.pt`, which is not in git):

```bash
uv run innersight camera            # read cards aloud; --mute for no speech
uv run innersight game --cards 10   # blindfolded guessing game
uv run innersight image hand.jpg --output annotated.jpg
uv run innersight capture           # record a training dataset
uv run innersight review            # review and re-capture recordings
```

Flutter (run from `mobile/`):

```bash
flutter analyze
flutter test
flutter test test/guessing_test.dart
flutter test --plain-name "swipeOutcome"        # tests whose name contains this
```

`flutter analyze` reports a `deprecated_member_use` info for every `package:flutter/material.dart`
import; those are known and not caused by your change. Do not run `dart format` over the whole of
`mobile/`: existing files are not formatted with it, so it rewrites files you did not touch.
Format only the files you edit.

Training and exporting the model:

```bash
uv run python scripts/add_upside_down_images.py   # datasets/own-cards-both-ways
uv run yolo detect train data=datasets/own-cards-both-ways/data.yaml model=yolo26s.pt epochs=100 imgsz=640 fliplr=0.0 degrees=15.0
mkdir -p weights && cp runs/detect/train/weights/best.pt weights/own-cards.pt
uv run --group export python scripts/export_mobile_model.py --weights weights/own-cards.pt
```

`fliplr=0.0` is deliberate: a mirrored digit is not a real card. Training on the copy with
every image also turned upside down is deliberate too: without it the detector reads an
upside-down 9 as a 6. Compare old and new weights with
`uv run python scripts/measure_rank_reading.py --weights <file>` before replacing them.

Measuring the color reading on the recorded dataset (the file names hold the true colors); run
it before and after any change to `color.py`:

```bash
uv run python scripts/measure_color_reading.py
```

## Architecture

### Recognition pipeline (both implementations)

1. A **detector** finds each card and reads its **rank**. The YOLO classes are ranks only
   (`RANKS` in `cards.py`), never colors.
2. **Color** is read separately by HSV hue analysis of the middle of the detection box
   (`color.py` / `color_classifier.dart`). Back and wild ranks skip this and get a fixed color
   (`recognition.py`). When no single color dominates, the color is `UNKNOWN`.
3. `SettledCardWatcher` (`announcement.py` / `announcer.dart`) reports a card once it has been the
   surest card for `STABLE_FRAME_COUNT` frames in a row, and again only after it changes or
   leaves. `CardAnnouncer` speaks what the watcher reports. The watcher leaves out frames
   where the color is `UNKNOWN`, so a card such as "unknown 5" is never announced or guessed.

Consequences worth knowing:

- "Confidence" is the detector's confidence in the **rank**. The color has no confidence value.
- `RANKS` is in class-id order and is written into recorded label files. New ranks go last;
  reordering silently relabels an existing dataset.
- `SPOKEN_RANKS` must cover every rank (a test enforces it).

### The Python/mobile contract

`scripts/export_mobile_model.py` writes `mobile/assets/models/own-cards.onnx` and
`model_config.json` from the Python constants (`RANKS`, `WILD_RANKS`, `BACK_RANK`,
`SPOKEN_RANKS`). The app reads ranks and spoken wording from that config, so a change to those
constants needs a re-export. `ModelConfig.defaults()` and `defaultSpokenRanks` in
`mobile/lib/src/cards.dart` are hand-written copies used as fallbacks and in tests; update them
too. The `.onnx` file is ignored by git, the config is not.

Logic that exists on both sides (watcher, announcer, guessing session, color classification,
spoken names) should be changed on both sides in the same change, with the matching test.

### Guessing game

`GuessingSession` (`guessing.py` / `guessing.dart`) is the whole game as a state machine with an
injected `say` callback and no I/O. A round starts when a card settles in view; the player gives
any number of answers, the last one counts when they lock in. While a round is open, another
reading replaces its card only if it settles within `CORRECTION_SECONDS` of the first reading
and the detector is surer of it; that drops the answer given so far. Otherwise other cards that
come into view are ignored. The back of a card is spoken but starts no round. The session takes
its clock as a parameter, so tests control the time. The player is blindfolded, so every state
change must be spoken.

The input layers are thin: `game.py` maps arrow keys and `SPACE` to the session and appends each
locked round to a CSV through `GuessLog`; `game_screen.dart` maps swipes (`swipeOutcome`) and a
double-tap. The phone has no file log; its result board shows the same data.

The session holds no images. `observe` returns the card of the round when it starts or is
corrected; the input layer crops that card from the frame and keeps one picture for every
locked round, which the result board shows beside the round. The pictures are kept in memory
only.

### Python conventions that are easy to miss

- Interactive loops take `frames` (an iterator) and `show` (a callable that displays a frame and
  returns the pressed key) as parameters. Tests drive them with `ScriptedWindow` and a repeated
  black frame from `tests/fakes.py`; no test opens a camera or window. Keep new loops in this
  shape.
- `show_frame` returns a one-byte key code, which cannot tell arrow keys from letters.
  `show_frame_for_key_code` returns the full `waitKeyEx` code and is what the game uses. Arrow
  codes differ by platform (`game.py`).
- Failures meant for the user are subclasses of `InnerSightError` (`errors.py`); `cli.main`
  prints them without a traceback.
- `speech.py` is imported lazily inside `cli.py` because loading the TTS model is slow. Keep it
  out of module-level imports of anything the other commands use.
- A banner has room for exactly `BANNER_LINE_COUNT` (4) lines (`banner.py`).
- Test names are sentences describing behavior (`test_does_not_lock_in_before_a_card_is_read`).
- Ruff line length is 100.

### Mobile structure

`CardCameraView` (`card_camera_view.dart`) owns the camera, the detector and the preview with
card outlines, and reports each recognized frame through `onCards`. Screens wrap it and decide
what to do with the cards: `CameraRecognitionScreen` announces them, `GameScreen` feeds a
`GuessingSession`. Screens reach `switchCamera()` through a `GlobalKey<CardCameraViewState>`.

Camera open, switch and dispose calls are serialized through one queue in `CardCameraView`, and
the camera is suspended only on `paused`, not `inactive`, because the permission dialog triggers
`inactive`. Both are fixes for real CameraX crashes; preserve them when editing that file.

The app is locked to portrait. `frame_prep.dart` rotates the sensor image upright and letterboxes
it; detection boxes are in upright-frame pixels.

## Data that stays local

`datasets/`, `runs/`, `logs/`, `*.pt` and the `.onnx` model are ignored by git. The dataset
images show the user and their room. The intended use is one card held up to the camera at a
time, trained on the user's own deck.
