from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import cv2

from config import (
    CRUISE_ALT_M,
    FALLBACK_RECOVERY,
    LOITER_RADIUS_M,
    PRIMARY_RECOVERY,
    RECOVERY_ALT_M,
    TAKEOFF_ALT_M,
    VideoConfig,
)
from flight_adapters.base import FlightControllerAdapter, VideoFrame
from schemas import (
    DetectorState,
    GeofencePolygon,
    LatLon,
    RoutePreview,
    RouteProgress,
    SimulatorState,
    StatePayload,
    TelemetrySnapshot,
)

from .detector_service import DetectorService
from .safety_manager import geofence_contains, should_trigger_battery_rtl


@dataclass
class VideoRuntime:
    encoded_jpeg: bytes
    fps: float
    latency_ms: float
    width: int
    height: int


class ArrakisController:
    def __init__(self, adapter: FlightControllerAdapter) -> None:
        self.adapter = adapter
        self.detector = DetectorService()
        self.phase = "IDLE"
        self.abort_reason: str | None = None
        self.route_preview: RoutePreview | None = None
        self.telemetry = TelemetrySnapshot(
            timestamp=time.time(),
            lat=adapter.get_home().lat,
            lon=adapter.get_home().lon,
            alt_m=0.0,
            airspeed_mps=0.0,
            groundspeed_mps=0.0,
            battery_percent=100.0,
            armed=False,
            flight_mode="STANDBY",
            vtol_state="MC",
            mission_index=-1,
            home_distance_m=0.0,
            geofence_breached=False,
            sim_rtf=1.0,
        )
        self.video = VideoRuntime(encoded_jpeg=b"", fps=0.0, latency_ms=0.0, width=1280, height=720)
        self._lock = threading.Lock()
        self._mission_thread: threading.Thread | None = None
        self._recovery_entered_at: float | None = None
        self._fallback_attempted = False

        self.adapter.connect()
        self.adapter.stream_telemetry(self._on_telemetry)
        self.adapter.stream_video(self._on_video)

    def _is_terminal_phase(self) -> bool:
        return self.phase in {"IDLE", "COMPLETE", "ABORT_GEOFENCE", "ABORT_MANUAL"}

    def set_route(self, preview: RoutePreview) -> RoutePreview:
        with self._lock:
            if self._mission_thread and self._mission_thread.is_alive() and not self._is_terminal_phase():
                raise RuntimeError("Mission is active. Reset or abort before uploading a new route.")
            self.route_preview = preview
            self.phase = "IDLE"
            self.abort_reason = None
            self._fallback_attempted = False
        return preview

    def start_mission(self) -> None:
        with self._lock:
            if self.route_preview is None:
                raise ValueError("Route must be set before starting a mission.")
            if self._mission_thread and self._mission_thread.is_alive():
                return
            if self.phase not in {"IDLE", "COMPLETE", "ABORT_GEOFENCE", "ABORT_MANUAL"}:
                raise RuntimeError("Mission is not in a startable state.")
            self.abort_reason = None
        self._mission_thread = threading.Thread(target=self._run_mission, daemon=True)
        self._mission_thread.start()

    def abort(self, reason: str = "manual operator abort") -> None:
        with self._lock:
            self.phase = "ABORT_MANUAL"
            self.abort_reason = reason
        self.adapter.abort(reason)

    def rtl(self) -> None:
        with self._lock:
            self.phase = "RTL_BATTERY"
            self.abort_reason = "manual rtl requested"
        self.adapter.return_to_home()

    def reset(self) -> None:
        self.adapter.reset()
        self.detector.clear()
        with self._lock:
            self.phase = "IDLE"
            self.abort_reason = None
            self.route_preview = None
            self._fallback_attempted = False
            self.telemetry = self.adapter.get_snapshot()
            self.video = VideoRuntime(
                encoded_jpeg=b"",
                fps=0.0,
                latency_ms=0.0,
                width=self.video.width,
                height=self.video.height,
            )

    def state_payload(self) -> StatePayload:
        with self._lock:
            detector = self.detector.export()
            progress = RouteProgress(
                outbound_total=len(self.route_preview.outbound) if self.route_preview else 0,
                return_total=len(self.route_preview.return_path) if self.route_preview else 0,
                current_leg=self.adapter.current_leg() if hasattr(self.adapter, "current_leg") else "idle",
                current_waypoint_index=self.telemetry.mission_index,
                next_waypoint=self._next_waypoint(),
            )
            sim = SimulatorState(
                connected=True,
                camera_connected=bool(self.video.encoded_jpeg),
                rtf=self.telemetry.sim_rtf,
                video_fps=self.video.fps,
                video_latency_ms=self.video.latency_ms,
            )
            return StatePayload(
                timestamp=time.time(),
                mission_phase=self.phase,
                abort_reason=self.abort_reason,
                telemetry=self.telemetry,
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
                geofence=self.route_preview.geofence if self.route_preview else None,
                route_home=self.route_preview.home if self.route_preview else None,
                outbound=self.route_preview.outbound if self.route_preview else [],
                return_path=self.route_preview.return_path if self.route_preview else [],
            )

    def latest_jpeg(self) -> bytes:
        with self._lock:
            return self.video.encoded_jpeg

    def _next_waypoint(self) -> LatLon | None:
        if not self.route_preview:
            return None
        route = self.route_preview.outbound + self.route_preview.return_path
        if 0 <= self.telemetry.mission_index < len(route):
            return route[self.telemetry.mission_index]
        return self.route_preview.home

    def _on_telemetry(self, snapshot: TelemetrySnapshot) -> None:
        with self._lock:
            geofence_breached = not geofence_contains(self.route_preview.geofence if self.route_preview else None, snapshot)
            snapshot = snapshot.model_copy(update={"geofence_breached": geofence_breached})
            self.telemetry = snapshot
        if should_trigger_battery_rtl(snapshot) and self.phase not in {"RTL_BATTERY", "LANDING", "COMPLETE"}:
            with self._lock:
                self.phase = "RTL_BATTERY"
                self.abort_reason = "battery threshold reached"
            self.adapter.return_to_home()
        if geofence_breached and self.phase not in {"ABORT_GEOFENCE", "LANDING", "COMPLETE"}:
            with self._lock:
                self.phase = "ABORT_GEOFENCE"
                self.abort_reason = "route-derived geofence breached"
            self.adapter.abort("geofence breach")

        # Degrade detector as simulation quality drops.
        if snapshot.sim_rtf < 0.7:
            self.detector.set_degrade_step(2)
        elif snapshot.sim_rtf < 0.9:
            self.detector.set_degrade_step(1)
        else:
            self.detector.set_degrade_step(0)

    def _on_video(self, frame: VideoFrame) -> None:
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
            self.video = VideoRuntime(
                encoded_jpeg=encoded.tobytes(),
                fps=frame.fps,
                latency_ms=frame.latency_ms,
                width=annotated.shape[1],
                height=annotated.shape[0],
            )

    def _run_mission(self) -> None:
        assert self.route_preview is not None
        self.phase = "ARMING"
        self.adapter.arm()
        time.sleep(1.0)

        self.phase = "TAKEOFF_MC"
        self.adapter.takeoff_multicopter(TAKEOFF_ALT_M)
        time.sleep(1.0)

        self.phase = "TRANSITION_FW"
        self.adapter.transition_to_fixedwing()
        self.adapter.upload_roundtrip_mission(
            {
                "outbound": [point.model_dump() for point in self.route_preview.outbound],
                "return_path": [point.model_dump() for point in self.route_preview.return_path],
                "geofence": [point.model_dump() for point in self.route_preview.geofence.coordinates],
            }
        )
        self.adapter.start_mission()
        self.phase = "OUTBOUND"

        # Track outbound/return and trigger recovery near the end.
        while True:
            state = self.state_payload()
            if state.mission_phase in {"ABORT_GEOFENCE", "RTL_BATTERY", "ABORT_MANUAL"}:
                return
            if state.route_progress.current_leg == "return":
                self.phase = "RETURN"
            if state.route_progress.current_leg == "idle" and state.telemetry.home_distance_m <= 120:
                break
            time.sleep(0.2)

        self.phase = "PRE_MC_RECOVERY"
        self.adapter.prepare_multicopter_recovery(
            {
                "recovery_center": self.route_preview.home.model_dump(),
                "target_alt_m": RECOVERY_ALT_M,
                "loiter_radius_m": LOITER_RADIUS_M,
            }
        )
        if not self._wait_for_recovery(PRIMARY_RECOVERY, False):
            if self.abort_reason:
                return
            self.adapter.return_to_home()
            if not self._wait_for_recovery(FALLBACK_RECOVERY, True):
                self.phase = "ABORT_MANUAL"
                self.abort_reason = "operator intervention required after recovery fallback"
                return

        self.phase = "TRANSITION_MC"
        self.adapter.transition_to_multicopter()
        time.sleep(1.0)
        self.phase = "LANDING"
        self.adapter.land_vertical()

        while self.telemetry.armed and self.telemetry.alt_m > 0.5:
            time.sleep(0.2)
        self.phase = "COMPLETE"

    def _wait_for_recovery(self, thresholds, fallback: bool) -> bool:
        deadline = time.time() + thresholds.timeout_seconds
        stable_since: float | None = None
        while time.time() < deadline:
            telemetry = self.telemetry
            if telemetry.geofence_breached:
                self.phase = "ABORT_GEOFENCE"
                self.abort_reason = "route-derived geofence breached"
                return False
            if should_trigger_battery_rtl(telemetry):
                self.phase = "RTL_BATTERY"
                self.abort_reason = "battery threshold reached"
                return False
            conditions_met = (
                telemetry.airspeed_mps <= thresholds.speed_threshold_mps
                and telemetry.home_distance_m <= thresholds.home_distance_threshold_m
                and abs(telemetry.alt_m - RECOVERY_ALT_M) <= thresholds.altitude_deviation_m
            )
            if conditions_met:
                stable_since = stable_since or time.time()
                if time.time() - stable_since >= thresholds.dwell_seconds:
                    return True
            else:
                stable_since = None
            time.sleep(0.2)
        return False
