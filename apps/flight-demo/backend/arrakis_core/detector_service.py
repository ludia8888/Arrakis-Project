from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field

from config import DEFAULT_MODEL_CANDIDATES
from schemas import DetectionBox, DetectorEvent

from .perception_backends.base import InferenceResult, PerceptionBackend, resolve_model_path
from .perception_backends.synthetic_backend import SyntheticPerceptionBackend
from .perception_backends.yolo_backend import YoloPerceptionBackend


logger = logging.getLogger("arrakis.detector")


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
        self._fallback_backend = SyntheticPerceptionBackend()
        self._active_backend = self._create_backend()
        self.runtime.mode = self._active_backend.mode
        logger.info("Detector backend selected: %s", self.runtime.mode)
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
            if self.runtime.degrade_step != step:
                logger.info("Detector degrade step %d -> %d", self.runtime.degrade_step, step)
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
        logger.info("Detector runtime cleared")

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
            result = self._infer(frame, metadata, degrade)
            inference_ms = (time.time() - started) * 1000.0
            events = [
                DetectorEvent(timestamp=time.time(), label=det.label, confidence=det.confidence, note="visible in camera")
                for det in result.detections
            ]
            with self._lock:
                self.runtime.mode = result.mode
                self.runtime.last_inference_ms = inference_ms
                self.runtime.current_detections = result.detections
                merged = [*self.runtime.recent_events, *events]
                cutoff = time.time() - 10.0
                self.runtime.recent_events = [event for event in merged if event.timestamp >= cutoff][-20:]
            logger.debug(
                "Inference complete mode=%s detections=%d latency=%.1fms queue_age=%.1fms",
                result.mode,
                len(result.detections),
                inference_ms,
                (time.time() - submitted_at) * 1000.0,
            )

    def _create_backend(self) -> PerceptionBackend:
        model_path = resolve_model_path(DEFAULT_MODEL_CANDIDATES)
        if model_path and model_path.suffix == ".pt":
            try:
                logger.info("Attempting YOLO backend with model=%s", model_path)
                return YoloPerceptionBackend(model_path)
            except Exception as exc:
                logger.exception("YOLO backend init failed, falling back to synthetic: %s", exc)
                return self._fallback_backend
        logger.info("No valid model found, using synthetic backend")
        return self._fallback_backend

    def _infer(self, frame, metadata: dict[str, object], degrade: int) -> InferenceResult:
        result = self._active_backend.infer(frame, metadata, degrade)
        if result.detections:
            return result
        fallback = self._fallback_backend.infer(frame, metadata, degrade)
        return fallback if fallback.detections else result
