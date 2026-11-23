# InnerSight

Recognizes UNO cards in images and live video. A fine-tuned YOLO detector finds each card and
reads its rank, and HSV color analysis reads its color.

## Setup

```bash
uv sync
```

## Train the detector

No trained weights are included, so the detector has to be trained before anything runs.

1. Get a UNO card dataset in YOLO format, labeled by rank (`0`–`9`, `skip`, `reverse`, `+2`,
   `wild`, `+4`). Roboflow Universe hosts public ones; check their classes and licence. The class
   names of the dataset become the ranks InnerSight reports.
2. Train a nano model on it:

   ```bash
   uv run yolo detect train data=datasets/uno/data.yaml model=yolo26n.pt epochs=100 imgsz=640
   ```

Training prints where it saved the weights, normally `runs/detect/train/weights/best.pt`.

The detector does not learn color, so the default color augmentation is fine.

## Run

On one image, printing the cards and saving an annotated copy:

```bash
uv run innersight image hand.jpg --weights runs/detect/train/weights/best.pt --output annotated.jpg
```

On a live camera feed (press `q` to quit):

```bash
uv run innersight camera --weights runs/detect/train/weights/best.pt
```

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
