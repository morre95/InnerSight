"""Find UNO cards and read their rank with a fine-tuned Ultralytics YOLO model."""

from pathlib import Path

import numpy as np
from ultralytics import YOLO

from innersight.cards import Box, Detection


class YoloCardDetector:
    def __init__(self, weights_path: Path, min_confidence: float) -> None:
        self._model = YOLO(weights_path)
        self._min_confidence = min_confidence

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        result = self._model.predict(frame_bgr, conf=self._min_confidence, verbose=False)[0]
        boxes = result.boxes.cpu().numpy()
        return [
            Detection(
                rank=result.names[int(class_id)],
                confidence=float(confidence),
                box=Box(*corners.round().astype(int).tolist()),
            )
            for corners, class_id, confidence in zip(boxes.xyxy, boxes.cls, boxes.conf, strict=True)
        ]
