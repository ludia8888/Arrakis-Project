from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import cv2

from config import VideoConfig
from flight_adapters.base import VideoFrame
from schemas import DetectorState, SimulatorState

from .detector_service import DetectorService


logger = logging.getLogger("arrakis.video")


@dataclass
class VideoRuntime:
    encoded_jpeg: bytes
    fps: float
    latency_ms: float
    width: int
    height: int


class VideoService:
    def __init__(self) -> None:
        self.detector = DetectorService()
        self._lock = threading.Lock()
        self._video_config = VideoConfig()
        self._video = VideoRuntime(encoded_jpeg=b"", fps=0.0, latency_ms=0.0, width=1280, height=720)

    def reset(self) -> None:
        self.detector.clear()
        with self._lock:
            width = self._video.width
            height = self._video.height
            self._video = VideoRuntime(
                encoded_jpeg=b"",
                fps=0.0,
                latency_ms=0.0,
                width=width,
                height=height,
            )
        logger.info("Video service reset")

    def latest_jpeg(self) -> bytes:
        with self._lock:
            return self._video.encoded_jpeg

    def set_degrade_from_rtf(self, sim_rtf: float) -> None:
        if sim_rtf < 0.7:
            self.detector.set_degrade_step(2)
        elif sim_rtf < 0.9:
            self.detector.set_degrade_step(1)
        else:
            self.detector.set_degrade_step(0)

    def on_video(self, frame: VideoFrame) -> None:
        self.detector.submit(frame.frame_bgr, frame.metadata)
        runtime = self.detector.export()
        annotated = frame.frame_bgr.copy()
        for det in runtime.current_detections:
            x1 = int(det.x1 * annotated.shape[1])
            y1 = int(det.y1 * annotated.shape[0])
            x2 = int(det.x2 * annotated.shape[1])
            y2 = int(det.y2 * annotated.shape[0])
            color = (90, 200, 255) if det.label == "vehicle" else (255, 220, 120)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                annotated,
                f"{det.label} {int(det.confidence * 100)}%",
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
            )
        ok, encoded = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), self._video_config.jpeg_quality])
        if not ok:
            return
        with self._lock:
            self._video = VideoRuntime(
                encoded_jpeg=encoded.tobytes(),
                fps=frame.fps,
                latency_ms=frame.latency_ms,
                width=annotated.shape[1],
                height=annotated.shape[0],
            )

    def detector_state(self) -> DetectorState:
        detector = self.detector.export()
        return DetectorState(
            enabled=detector.enabled,
            mode=detector.mode,
            last_inference_ms=detector.last_inference_ms,
            objects_visible=len(detector.current_detections),
            recent_events=detector.recent_events,
            current_detections=detector.current_detections,
        )

    def simulator_state(self, sim_rtf: float) -> SimulatorState:
        with self._lock:
            video = self._video
        return SimulatorState(
            connected=True,
            camera_connected=bool(video.encoded_jpeg),
            rtf=sim_rtf,
            video_fps=video.fps,
            video_latency_ms=video.latency_ms,
        )
