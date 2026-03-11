from __future__ import annotations

import logging
from schemas import DetectionBox

from .base import InferenceResult, PerceptionBackend


logger = logging.getLogger("arrakis.perception.synthetic")


class SyntheticPerceptionBackend(PerceptionBackend):
    @property
    def mode(self) -> str:
        return "synthetic"

    def infer(self, frame, metadata: dict[str, object], degrade_step: int) -> InferenceResult:
        logger.debug("Running synthetic inference degrade_step=%d metadata_items=%d", degrade_step, len(metadata.get("synthetic_detections", [])))
        detections: list[DetectionBox] = []
        for item in metadata.get("synthetic_detections", []):
            detections.append(
                DetectionBox(
                    label=item["label"],
                    confidence=float(item["confidence"]),
                    x1=float(item["x1"]),
                    y1=float(item["y1"]),
                    x2=float(item["x2"]),
                    y2=float(item["y2"]),
                )
            )
        return InferenceResult(detections=detections, mode=self.mode)
