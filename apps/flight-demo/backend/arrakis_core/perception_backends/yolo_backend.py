from __future__ import annotations

import logging
from pathlib import Path

from schemas import DetectionBox

from .base import InferenceResult, PerceptionBackend

try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover
    YOLO = None


logger = logging.getLogger("arrakis.perception.yolo")


class YoloPerceptionBackend(PerceptionBackend):
    def __init__(self, model_path: Path) -> None:
        if YOLO is None:
            raise RuntimeError("Ultralytics is not installed.")
        self._model_path = model_path
        logger.info("Loading YOLO perception backend from %s", model_path)
        self._model = YOLO(str(model_path))

    @property
    def mode(self) -> str:
        return f"yolo:{self._model_path.name}"

    def infer(self, frame, metadata: dict[str, object], degrade_step: int) -> InferenceResult:
        target = 960 if degrade_step == 0 else 768
        logger.debug("Running YOLO inference imgsz=%d degrade_step=%d", target, degrade_step)
        result = self._model.predict(frame, imgsz=target, verbose=False, conf=0.25)[0]
        detections: list[DetectionBox] = []
        for box in result.boxes or []:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            label = str(result.names[int(box.cls.item())])
            if label not in {"person", "vehicle"}:
                continue
            detections.append(
                DetectionBox(
                    label=label,
                    confidence=float(box.conf.item()),
                    x1=float(x1 / frame.shape[1]),
                    y1=float(y1 / frame.shape[0]),
                    x2=float(x2 / frame.shape[1]),
                    y2=float(y2 / frame.shape[0]),
                )
            )
        return InferenceResult(detections=detections, mode=self.mode)
