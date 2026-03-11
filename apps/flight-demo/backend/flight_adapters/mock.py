from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np

from config import CRUISE_ALT_M, RECOVERY_ALT_M, TAKEOFF_ALT_M, VideoConfig
from schemas import LatLon, TelemetrySnapshot

from .base import FlightControllerAdapter, VideoFrame


logger = logging.getLogger("arrakis.adapter.mock")


def _project(home: LatLon, point: LatLon) -> tuple[float, float]:
    lat_scale = 111_320.0
    lon_scale = math.cos(math.radians(home.lat)) * 111_320.0
    return ((point.lon - home.lon) * lon_scale, (point.lat - home.lat) * lat_scale)


def _unproject(home: LatLon, x_m: float, y_m: float) -> LatLon:
    lat_scale = 111_320.0
    lon_scale = math.cos(math.radians(home.lat)) * 111_320.0
    return LatLon(lat=home.lat + y_m / lat_scale, lon=home.lon + x_m / lon_scale)


def _distance_m(a: LatLon, b: LatLon) -> float:
    ax, ay = _project(a, a)
    bx, by = _project(a, b)
    return math.hypot(bx - ax, by - ay)


@dataclass
class SimState:
    lat: float
    lon: float
    alt_m: float = 0.0
    airspeed_mps: float = 0.0
    groundspeed_mps: float = 0.0
    battery_percent: float = 100.0
    armed: bool = False
    flight_mode: str = "STANDBY"
    vtol_state: str = "MC"
    mission_index: int = -1
    geofence_breached: bool = False
    sim_rtf: float = 1.0


class MockAdapter(FlightControllerAdapter):
    def __init__(self) -> None:
        self.home = LatLon(lat=37.5665, lon=126.9780)
        self.state = SimState(lat=self.home.lat, lon=self.home.lon)
        self._video_callbacks: list[Callable[[VideoFrame], None]] = []
        self._telemetry_callbacks: list[Callable[[TelemetrySnapshot], None]] = []
        self._lock = threading.Lock()
        self._running = False
        self._mission_points: list[LatLon] = []
        self._route_leg = "idle"
        self._recovery_active = False
        self._landing_active = False
        self._returning_home = False
        self._video_cfg = VideoConfig()
        self._last_video_ts = 0.0
        self._synthetic_objects = [
            {"label": "vehicle", "x": 160.0, "y": 220.0, "vx": 8.0, "vy": 0.0, "w": 120.0, "h": 60.0},
            {"label": "person", "x": 900.0, "y": 380.0, "vx": -5.0, "vy": 0.0, "w": 36.0, "h": 96.0},
        ]

    def connect(self) -> None:
        if self._running:
            return
        self._running = True
        logger.info("Starting mock adapter loops")
        threading.Thread(target=self._telemetry_loop, daemon=True).start()
        threading.Thread(target=self._video_loop, daemon=True).start()

    def arm(self) -> None:
        logger.info("Mock arm")
        with self._lock:
            self.state.armed = True
            self.state.flight_mode = "ARMED"

    def takeoff_multicopter(self, target_alt_m: float) -> None:
        logger.info("Mock takeoff_multicopter target_alt_m=%.1f", target_alt_m)
        with self._lock:
            self.state.flight_mode = "TAKEOFF"
            self.state.vtol_state = "MC"
            self.state.alt_m = max(self.state.alt_m, target_alt_m)
            self.state.airspeed_mps = 4.0
            self.state.groundspeed_mps = 4.0

    def upload_roundtrip_mission(self, route_spec: dict[str, object]) -> None:
        outbound = [LatLon(**item) if isinstance(item, dict) else item for item in route_spec["outbound"]]
        return_path = [LatLon(**item) if isinstance(item, dict) else item for item in route_spec["return_path"]]
        logger.info("Mock upload_roundtrip_mission outbound=%d return=%d", len(outbound), len(return_path))
        with self._lock:
            self._mission_points = outbound + return_path
            self._route_leg = "outbound"
            self.state.mission_index = 0

    def start_mission(self) -> None:
        logger.info("Mock start_mission")
        with self._lock:
            self.state.flight_mode = "MISSION"
            self.state.vtol_state = "FW"
            self.state.alt_m = CRUISE_ALT_M
            self.state.airspeed_mps = 22.0
            self.state.groundspeed_mps = 20.0

    def transition_to_fixedwing(self) -> None:
        logger.info("Mock transition_to_fixedwing")
        with self._lock:
            self.state.vtol_state = "FW"
            self.state.flight_mode = "TRANSITION_FW"
            self.state.airspeed_mps = 18.0
            self.state.groundspeed_mps = 16.0
            self.state.alt_m = max(self.state.alt_m, CRUISE_ALT_M)

    def prepare_multicopter_recovery(self, recovery_spec: dict[str, object]) -> None:
        logger.info("Mock prepare_multicopter_recovery target_alt_m=%s", recovery_spec.get("target_alt_m", RECOVERY_ALT_M))
        with self._lock:
            self._recovery_active = True
            self.state.flight_mode = "LOITER"
            self.state.alt_m = recovery_spec.get("target_alt_m", RECOVERY_ALT_M)

    def transition_to_multicopter(self) -> None:
        logger.info("Mock transition_to_multicopter")
        with self._lock:
            self._recovery_active = False
            self.state.vtol_state = "MC"
            self.state.flight_mode = "TRANSITION_MC"
            self.state.airspeed_mps = 9.0
            self.state.groundspeed_mps = 8.0

    def return_to_home(self) -> None:
        logger.info("Mock return_to_home")
        with self._lock:
            self._returning_home = True
            self.state.flight_mode = "RTL"
            self.state.vtol_state = "FW"
            self.state.airspeed_mps = max(self.state.airspeed_mps, 16.0)
            self.state.groundspeed_mps = max(self.state.groundspeed_mps, 14.0)

    def land_vertical(self) -> None:
        logger.info("Mock land_vertical")
        with self._lock:
            self._landing_active = True
            self.state.flight_mode = "LAND"
            self.state.vtol_state = "MC"

    def abort(self, reason: str) -> None:
        logger.warning("Mock abort reason=%s", reason)
        self.return_to_home()
        with self._lock:
            self.state.flight_mode = f"ABORT:{reason}"

    def reset(self) -> None:
        logger.info("Mock reset")
        with self._lock:
            self.state = SimState(lat=self.home.lat, lon=self.home.lon)
            self._mission_points = []
            self._route_leg = "idle"
            self._recovery_active = False
            self._landing_active = False
            self._returning_home = False

    def get_snapshot(self) -> TelemetrySnapshot:
        with self._lock:
            return self._snapshot_locked()

    def stream_telemetry(self, callback: Callable[[TelemetrySnapshot], None]) -> None:
        logger.info("Mock telemetry subscriber registered")
        self._telemetry_callbacks.append(callback)

    def stream_video(self, callback: Callable[[VideoFrame], None]) -> None:
        logger.info("Mock video subscriber registered")
        self._video_callbacks.append(callback)

    def get_home(self) -> LatLon:
        return self.home

    def _snapshot_locked(self) -> TelemetrySnapshot:
        return TelemetrySnapshot(
            timestamp=time.time(),
            lat=self.state.lat,
            lon=self.state.lon,
            alt_m=self.state.alt_m,
            airspeed_mps=self.state.airspeed_mps,
            groundspeed_mps=self.state.groundspeed_mps,
            battery_percent=max(self.state.battery_percent, 0.0),
            armed=self.state.armed,
            flight_mode=self.state.flight_mode,
            vtol_state=self.state.vtol_state,
            mission_index=self.state.mission_index,
            home_distance_m=_distance_m(self.home, LatLon(lat=self.state.lat, lon=self.state.lon)),
            geofence_breached=self.state.geofence_breached,
            sim_rtf=self.state.sim_rtf,
        )

    def _telemetry_loop(self) -> None:
        last = time.time()
        while self._running:
            now = time.time()
            dt = max(now - last, 0.2)
            last = now
            with self._lock:
                self._step_locked(dt)
                snapshot = self._snapshot_locked()
            for callback in self._telemetry_callbacks:
                callback(snapshot)
            time.sleep(0.2)

    def _move_towards_locked(self, target: LatLon, speed_mps: float, dt: float) -> bool:
        sx, sy = _project(self.home, LatLon(lat=self.state.lat, lon=self.state.lon))
        tx, ty = _project(self.home, target)
        dx, dy = tx - sx, ty - sy
        distance = math.hypot(dx, dy)
        if distance < 1.0:
            self.state.lat = target.lat
            self.state.lon = target.lon
            return True
        step = min(speed_mps * dt, distance)
        nx, ny = sx + dx / distance * step, sy + dy / distance * step
        point = _unproject(self.home, nx, ny)
        self.state.lat, self.state.lon = point.lat, point.lon
        return step >= distance - 1.0

    def _step_locked(self, dt: float) -> None:
        self.state.battery_percent = max(0.0, self.state.battery_percent - 0.02 * dt * max(self.state.airspeed_mps, 2.0))
        if self._landing_active:
            self.state.alt_m = max(0.0, self.state.alt_m - 6.0 * dt)
            self.state.airspeed_mps = 4.0
            self.state.groundspeed_mps = 3.0
            if self.state.alt_m <= 0.5:
                self.state.alt_m = 0.0
                self.state.armed = False
                self.state.flight_mode = "COMPLETE"
                self._landing_active = False
            return

        if self._recovery_active:
            self.state.airspeed_mps = max(10.0, self.state.airspeed_mps - 2.8 * dt)
            self.state.groundspeed_mps = max(8.0, self.state.groundspeed_mps - 2.2 * dt)
            self._move_towards_locked(self.home, max(self.state.groundspeed_mps, 6.0), dt)
            self.state.alt_m = RECOVERY_ALT_M
            return

        if self._returning_home:
            self._move_towards_locked(self.home, max(self.state.groundspeed_mps, 12.0), dt)
            if _distance_m(self.home, LatLon(lat=self.state.lat, lon=self.state.lon)) <= 20.0:
                self._returning_home = False
                self.state.airspeed_mps = 12.0
                self.state.groundspeed_mps = 10.0
            return

        if self._mission_points and self.state.mission_index >= 0:
            target = self._mission_points[min(self.state.mission_index, len(self._mission_points) - 1)]
            reached = self._move_towards_locked(target, max(self.state.groundspeed_mps, 16.0), dt)
            if reached:
                self.state.mission_index += 1
                if self.state.mission_index >= len(self._mission_points):
                    self.state.mission_index = len(self._mission_points) - 1
                    self._mission_points = []
                elif self.state.mission_index >= max(1, len(self._mission_points) // 2):
                    self._route_leg = "return"

    def current_leg(self) -> str:
        with self._lock:
            return self._route_leg if self._mission_points else "idle"

    def _video_loop(self) -> None:
        while self._running:
            started = time.time()
            frame = self._build_frame()
            frame_obj = VideoFrame(
                timestamp=started,
                frame_bgr=frame,
                fps=float(self._video_cfg.fps),
                latency_ms=(time.time() - started) * 1000.0,
                metadata={"synthetic_detections": self._synthetic_detection_metadata()},
            )
            for callback in self._video_callbacks:
                callback(frame_obj)
            sleep_for = max(0.0, (1.0 / self._video_cfg.fps) - (time.time() - started))
            time.sleep(sleep_for)

    def _synthetic_detection_metadata(self) -> list[dict[str, float | str]]:
        for obj in self._synthetic_objects:
            obj["x"] += obj["vx"]
            if obj["x"] < 40 or obj["x"] + obj["w"] > self._video_cfg.width - 40:
                obj["vx"] *= -1
                obj["x"] += obj["vx"]
        detections = []
        for obj in self._synthetic_objects:
            detections.append(
                {
                    "label": obj["label"],
                    "confidence": 0.86 if obj["label"] == "vehicle" else 0.79,
                    "x1": obj["x"] / self._video_cfg.width,
                    "y1": obj["y"] / self._video_cfg.height,
                    "x2": (obj["x"] + obj["w"]) / self._video_cfg.width,
                    "y2": (obj["y"] + obj["h"]) / self._video_cfg.height,
                }
            )
        return detections

    def _build_frame(self) -> np.ndarray:
        frame = np.zeros((self._video_cfg.height, self._video_cfg.width, 3), dtype=np.uint8)
        frame[:] = (17, 30, 38)
        cv2.rectangle(frame, (0, 0), (self._video_cfg.width, self._video_cfg.height // 2), (80, 132, 195), -1)
        cv2.rectangle(frame, (0, self._video_cfg.height // 2), (self._video_cfg.width, self._video_cfg.height), (44, 88, 56), -1)
        cv2.putText(frame, "ARRAKIS VTOL MOCK CAMERA", (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (248, 244, 220), 2)
        cv2.putText(
            frame,
            f"mode={self.state.flight_mode} vtol={self.state.vtol_state} battery={self.state.battery_percent:.1f}%",
            (40, 105),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (248, 244, 220),
            2,
        )
        for obj in self._synthetic_objects:
            x1, y1 = int(obj["x"]), int(obj["y"])
            x2, y2 = int(obj["x"] + obj["w"]), int(obj["y"] + obj["h"])
            color = (80, 180, 255) if obj["label"] == "vehicle" else (255, 210, 80)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, obj["label"], (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        cx = int((time.time() * 50) % self._video_cfg.width)
        cy = self._video_cfg.height // 2
        cv2.line(frame, (cx - 18, cy), (cx + 18, cy), (255, 255, 255), 2)
        cv2.line(frame, (cx, cy - 18), (cx, cy + 18), (255, 255, 255), 2)
        return frame
