"""Export a fine-tuned YOLO checkpoint and card metadata for the Flutter Android app."""

import argparse
import json
import shutil
import urllib.request
from pathlib import Path

import onnxruntime as ort
from ultralytics import YOLO

from innersight.announcement import SPOKEN_RANKS
from innersight.cards import BACK_RANK, RANKS, WILD_RANKS

RELEASE_V010_URL = "https://github.com/morre95/InnerSight/releases/download/v0.1.0/own-cards.pt"
DEFAULT_WEIGHTS_PATH = Path("weights/own-cards-v0.1.0.pt")
DEFAULT_OUTPUT_DIR = Path("mobile/assets/models")
DEFAULT_IMGSZ = 640


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--weights",
        type=Path,
        default=None,
        help=(
            "Path to a .pt checkpoint. When omitted, downloads release v0.1.0 into "
            f"{DEFAULT_WEIGHTS_PATH} if needed."
        ),
    )
    parser.add_argument(
        "--release-url",
        default=RELEASE_V010_URL,
        help="URL used to fetch weights when --weights is omitted.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where own-cards.onnx and model_config.json are written.",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=DEFAULT_IMGSZ,
        help="Square input size in pixels for the exported ONNX graph.",
    )
    return parser.parse_args()


def ensure_weights(weights_path: Path | None, release_url: str) -> Path:
    if weights_path is not None:
        if not weights_path.is_file():
            raise FileNotFoundError(f"Checkpoint not found: {weights_path}")
        return weights_path

    target = DEFAULT_WEIGHTS_PATH
    if target.is_file():
        print(f"Using cached checkpoint at {target}")
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {release_url} -> {target} ...")
    urllib.request.urlretrieve(release_url, target)
    return target


def extract_model_ranks(model: YOLO) -> list[str]:
    names = model.names
    ordered = [names[index] for index in sorted(names)]
    if tuple(ordered) != RANKS:
        print(
            f"Note: checkpoint defines {len(ordered)} classes {ordered}; "
            f"innersight.cards.RANKS has {len(RANKS)} classes."
        )
    return ordered


def verify_onnx(onnx_path: Path, imgsz: int, num_classes: int) -> list[int]:
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    if len(inputs) != 1 or len(outputs) != 1:
        raise RuntimeError(
            f"Expected 1 input and 1 output tensor, got {len(inputs)} and {len(outputs)}"
        )

    input_shape = list(inputs[0].shape)
    output_shape = list(outputs[0].shape)
    expected_input = [1, 3, imgsz, imgsz]
    anchors = (imgsz // 8) ** 2 + (imgsz // 16) ** 2 + (imgsz // 32) ** 2
    expected_output = [1, 4 + num_classes, anchors]
    if input_shape != expected_input:
        raise RuntimeError(f"Unexpected ONNX input shape {input_shape}; expected {expected_input}")
    if output_shape != expected_output:
        raise RuntimeError(
            f"Unexpected ONNX output shape {output_shape}; expected {expected_output}"
        )
    return output_shape


def export_mobile_assets(weights_path: Path, output_dir: Path, imgsz: int) -> None:
    model = YOLO(weights_path)
    ranks = extract_model_ranks(model)

    # nms=None selects the raw one2many head ([1, 4 + nc, 8400]) matching desktop YOLO.predict,
    # while allowing runtime confidence thresholding and NMS in Dart.
    exported = Path(model.export(format="onnx", imgsz=imgsz, nms=None, simplify=True))

    output_dir.mkdir(parents=True, exist_ok=True)
    onnx_target = output_dir / "own-cards.onnx"
    if exported.resolve() != onnx_target.resolve():
        shutil.move(str(exported), str(onnx_target))

    output_shape = verify_onnx(onnx_target, imgsz=imgsz, num_classes=len(ranks))

    config = {
        "input_size": imgsz,
        "output_shape": output_shape,
        "ranks": ranks,
        "wild_ranks": list(WILD_RANKS),
        "back_rank": BACK_RANK,
        "spoken_ranks": SPOKEN_RANKS,
    }
    config_target = output_dir / "model_config.json"
    config_target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    size_mb = onnx_target.stat().st_size / (1024 * 1024)
    print(f"Exported {onnx_target} ({size_mb:.2f} MB, shape={output_shape})")
    print(f"Wrote {config_target} ({len(ranks)} classes)")


def main() -> None:
    args = parse_args()
    weights = ensure_weights(args.weights, args.release_url)
    export_mobile_assets(weights, args.output_dir, args.imgsz)


if __name__ == "__main__":
    main()
