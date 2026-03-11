from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2

from config import DEFAULT_MODEL_CANDIDATES
from schemas import DetectionBox, DetectorEvent

try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover
    YOLO = None


def resolve_model_path() -> Path | None:
    for path in DEFAULT_MODEL_CANDIDATES:
        if path.exists():
            return path
    return None


@dataclass
class DetectorRuntime:
    mode: str = "synthetic"
    enabled: bool = True
    last_inference_ms: float = 0.0
    current_detections: list[DetectionBox] = field(default_factory=list)
    recent_events: list[DetectorEvent] = field(default_factory=list)
    degrade_step: int = 0


class DetectorService:
    def __init__(self) -> None:
        self.runtime = DetectorRuntime()
        self._queue: queue.Queue = queue.Queue(maxsize=1)
        self._lock = threading.Lock()
        self._model = None
        self._model_path = resolve_model_path()
        if YOLO and self._model_path and self._model_path.suffix == ".pt":
            try:
                self._model = YOLO(str(self._model_path))
                self.runtime.mode = f"yolo:{self._model_path.name}"
            except Exception:
                self.runtime.mode = "synthetic"
        threading.Thread(target=self._loop, daemon=True).start()

    def submit(self, frame, metadata: dict[str, object]) -> None:
        payload = (frame, metadata, time.time())
        while True:
            try:
                self._queue.put_nowait(payload)
                break
            except queue.Full:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break

    def set_degrade_step(self, step: int) -> None:
        with self._lock:
            self.runtime.degrade_step = step

    def export(self) -> DetectorRuntime:
        with self._lock:
            return DetectorRuntime(
                mode=self.runtime.mode,
                enabled=self.runtime.enabled,
                last_inference_ms=self.runtime.last_inference_ms,
                current_detections=list(self.runtime.current_detections),
                recent_events=list(self.runtime.recent_events),
                degrade_step=self.runtime.degrade_step,
            )

    def clear(self) -> None:
        with self._lock:
            self.runtime.last_inference_ms = 0.0
            self.runtime.current_detections = []
            self.runtime.recent_events = []

    def _loop(self) -> None:
        frame_count = 0
        while True:
            frame, metadata, submitted_at = self._queue.get()
            frame_count += 1
            degrade = self.export().degrade_step
            cadence = 2 if degrade == 0 else 3
            if frame_count % cadence != 0:
                continue
            started = time.time()
            detections = self._infer(frame, metadata, degrade)
            inference_ms = (time.time() - started) * 1000.0
            events = [
                DetectorEvent(timestamp=time.time(), label=det.label, confidence=det.confidence, note="visible in camera")
                for det in detections
            ]
            with self._lock:
                self.runtime.last_inference_ms = inference_ms
                self.runtime.current_detections = detections
                merged = [*self.runtime.recent_events, *events]
                cutoff = time.time() - 10.0
                self.runtime.recent_events = [event for event in merged if event.timestamp >= cutoff][-20:]

    def _infer(self, frame, metadata: dict[str, object], degrade: int) -> list[DetectionBox]:
        if self._model is not None:
            target = 960 if degrade == 0 else 768
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
            if detections:
                return detections
            synthetic = self._synthetic_detections(metadata)
            if synthetic:
                return synthetic

        return self._synthetic_detections(metadata)

    def _synthetic_detections(self, metadata: dict[str, object]) -> list[DetectionBox]:
        synthetic = metadata.get("synthetic_detections", [])
        detections = []
        for item in synthetic:
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
        return detections
