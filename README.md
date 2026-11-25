# InnerSight

Recognizes the UNO card you hold up to a webcam and says it aloud. A fine-tuned YOLO detector
finds the card and reads its rank, HSV color analysis reads its color, and Pocket TTS speaks the
result.

## Setup

```bash
uv sync
```

On Linux, speech also needs the PortAudio system library (`portaudio` on Arch, `libportaudio2`
on Debian and Ubuntu).

## Record your own cards

No trained weights are included. The detector learns from images of your own deck, recorded with
your own webcam:

```bash
uv run innersight capture
```

To add a second dataset:

```bash
 uv run innersight capture --index 1 --dataset datasets/phone-cards
```

The tool walks through all 57 card designs, the back of a card and one step without a card. The
last three designs, wild shuffle, wild joker and wild customizable, are only in some decks. For each step it shows a
card-shaped outline at six different places in the picture:

1. Hold the card so it fills the outline, with your fingers covering as little of it as possible.
2. Press `SPACE`. It records a short burst of frames and moves the outline.

Press `S` to skip a card you do not have and `Q` to stop. Running the command again continues
with the positions that are not recorded yet.

The result is about 1,700 labeled images in `datasets/own-cards`, in the YOLO format. One position
of every card is held back for validation. The images show you and your room; `datasets/` is
ignored by git, so they stay on this machine.

## Review the recordings

```bash
uv run innersight review
```

The tool shows each recorded position as its five frames side by side, with a green box where
the label says the card is. Look for a card that does not fill the box, the wrong card, blur, or
fingers over the symbols.

- `SPACE` keeps the position and moves on.
- `R` marks it for re-capture.
- `B` goes back one position.
- `Q`, or closing the window, finishes the review.

When the review is finished, the camera opens and you record the marked positions again, the same
way as in `capture`. The old images are replaced only when the new ones are recorded, so stopping
early loses nothing.

## Train the detector

```bash
uv run yolo detect train data=datasets/own-cards/data.yaml model=yolo26n.pt epochs=100 imgsz=640 fliplr=0.0 degrees=15.0
```

- `fliplr=0.0` turns off mirroring, because a mirrored digit is not a real card.
- `degrees=15.0` rotates the training images, because the outline is always upright but real
  cards are held at an angle.

Training prints where it saved the weights, normally `runs/detect/train/weights/best.pt`. When
you are happy with them, copy them to where InnerSight looks by default:

```bash
mkdir -p weights && cp runs/detect/train/weights/best.pt weights/own-cards.pt
```

Add the wheights to flutter app:
```bash
uv run python scripts/export_mobile_model.py --weights weights/own-cards.pt
```

`*.pt` files are ignored by git, so the weights stay on this machine. To try other weights
without replacing these, add `--weights path/to/best.pt` to the commands below.

The detector does not learn color, so the default color augmentation is fine.

## Run

On a live camera feed (press `q` to quit):

```bash
uv run innersight camera
```

When a card has been in view for a few frames, its color and rank are spoken in English, for
example "red seven" or "wild draw four". A card held with its back to the camera is spoken as
"card back". The card is spoken again only after it changes or leaves
the picture. Add `--mute` to turn speech off.

The first run downloads the Pocket TTS model, about 225 MB, from Hugging Face. The voice is set
by `VOICE` in [speech.py](src/innersight/speech.py); each Pocket TTS voice has its own licence,
listed at [kyutai/tts-voices](https://huggingface.co/kyutai/tts-voices).

On one image, printing the cards and saving an annotated copy:

```bash
uv run innersight image hand.jpg --output annotated.jpg
```

## Play the guessing game

Guess the card you hold while blindfolded, then tell the game how the guess went:

```bash
uv run innersight game --cards 10
```

`--cards` is how many cards the session has. Everything is spoken, so you can play without
seeing the screen:

1. Guess, then hold the card up to the camera. The voice reads it.
2. Answer with the arrow keys. The voice says what each key means, so you can press several;
   the last one counts.

   | Key   | Answer      |
   | ----- | ----------- |
   | Up    | both right  |
   | Left  | color right |
   | Right | rank right  |
   | Down  | miss        |

3. Press `SPACE` to lock in the answer, then take the card away and hold up the next one.
   The voice says "Next card", or "Last card" when one card is left.

After the last card the voice says the result and a result board shows the count of every
answer and every card. Each card is shown with a picture cut from the camera frame it was read
in, so you can check that the detector read it correctly. `Q` ends the session early. Every round is added to `logs/guesses.csv`
with the card the detector read and how sure it was; `--log` chooses another file.

In the phone app, choose the number of cards and press Start game. Swipe up, left, right or
down for the same answers as the arrow keys, and double-tap to lock in. Its result board shows
the same pictures of the cards.

## Calibrate the colors

The hue ranges and thresholds in [color.py](src/innersight/color.py) are starting values. Warm
indoor light pushes yellow toward red and green toward yellow, so adjust `HUE_RANGES` to your
own deck, camera and lighting. A card with no single dominant color is reported as `wild`.

## Development

```bash
uv run pytest
```

```bash
uv run ruff check
```

```bash
uv run ruff format --check
```

## Licence

InnerSight is MIT licensed. It depends on [Ultralytics](https://github.com/ultralytics/ultralytics),
which is AGPL-3.0: distributing InnerSight together with it brings AGPL obligations unless you
hold an Ultralytics enterprise licence.
