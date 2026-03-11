from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import cv2

from config import VideoConfig
from flight_adapters.base import VideoFrame
from schemas import (
    DetectorState,
    LatLon,
    RoutePreview,
    RouteProgress,
    SimulatorState,
    StatePayload,
    TelemetrySnapshot,
)

from .detector_service import DetectorService
from .safety_manager import geofence_contains, should_trigger_battery_rtl


@dataclass(frozen=True)
class SafetyDecision:
    trigger_battery_rtl: bool
    trigger_geofence_abort: bool


@dataclass
class VideoRuntime:
    encoded_jpeg: bytes
    fps: float
    latency_ms: float
    width: int
    height: int


class TelemetryHub:
    def __init__(self, initial_snapshot: TelemetrySnapshot) -> None:
        self.detector = DetectorService()
        self._lock = threading.Lock()
        self._telemetry = initial_snapshot
        self._video = VideoRuntime(encoded_jpeg=b"", fps=0.0, latency_ms=0.0, width=1280, height=720)

    def reset(self, snapshot: TelemetrySnapshot) -> None:
        self.detector.clear()
        with self._lock:
            self._telemetry = snapshot
            self._video = VideoRuntime(
                encoded_jpeg=b"",
                fps=0.0,
                latency_ms=0.0,
                width=self._video.width,
                height=self._video.height,
            )

    def telemetry_snapshot(self) -> TelemetrySnapshot:
        with self._lock:
            return self._telemetry

    def latest_jpeg(self) -> bytes:
        with self._lock:
            return self._video.encoded_jpeg

    def on_telemetry(self, snapshot: TelemetrySnapshot, route_preview: RoutePreview | None) -> SafetyDecision:
        geofence_breached = not geofence_contains(route_preview.geofence if route_preview else None, snapshot)
        updated = snapshot.model_copy(update={"geofence_breached": geofence_breached})
        with self._lock:
            self._telemetry = updated

        if updated.sim_rtf < 0.7:
            self.detector.set_degrade_step(2)
        elif updated.sim_rtf < 0.9:
            self.detector.set_degrade_step(1)
        else:
            self.detector.set_degrade_step(0)

        return SafetyDecision(
            trigger_battery_rtl=should_trigger_battery_rtl(updated),
            trigger_geofence_abort=geofence_breached,
        )

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
        ok, encoded = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), VideoConfig().jpeg_quality])
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

    def state_payload(
        self,
        *,
        mission_phase,
        abort_reason: str | None,
        route_preview: RoutePreview | None,
        current_leg: str,
    ) -> StatePayload:
        with self._lock:
            telemetry = self._telemetry
            video = self._video
        detector = self.detector.export()
        progress = RouteProgress(
            outbound_total=len(route_preview.outbound) if route_preview else 0,
            return_total=len(route_preview.return_path) if route_preview else 0,
            current_leg=current_leg,
            current_waypoint_index=telemetry.mission_index,
            next_waypoint=self._next_waypoint(route_preview, telemetry.mission_index),
        )
        sim = SimulatorState(
            connected=True,
            camera_connected=bool(video.encoded_jpeg),
            rtf=telemetry.sim_rtf,
            video_fps=video.fps,
            video_latency_ms=video.latency_ms,
        )
        return StatePayload(
            timestamp=time.time(),
            mission_phase=mission_phase,
            abort_reason=abort_reason,
            telemetry=telemetry,
            route_progress=progress,
            detector=DetectorState(
                enabled=detector.enabled,
                mode=detector.mode,
                last_inference_ms=detector.last_inference_ms,
                objects_visible=len(detector.current_detections),
                recent_events=detector.recent_events,
                current_detections=detector.current_detections,
            ),
            simulator=sim,
            geofence=route_preview.geofence if route_preview else None,
            route_home=route_preview.home if route_preview else None,
            outbound=route_preview.outbound if route_preview else [],
            return_path=route_preview.return_path if route_preview else [],
        )

    def _next_waypoint(self, route_preview: RoutePreview | None, mission_index: int) -> LatLon | None:
        if not route_preview:
            return None
        route = route_preview.outbound + route_preview.return_path
        if 0 <= mission_index < len(route):
            return route[mission_index]
        return route_preview.home
