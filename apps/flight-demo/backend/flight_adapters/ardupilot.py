from __future__ import annotations

import importlib
import logging
import math
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Callable

from airframe_profile import AirframeProfile
from config import (
    ARDUPILOT_COMMAND_TIMEOUT,
    ARDUPILOT_CONNECTION,
    ARDUPILOT_DEFAULT_HOME_LAT,
    ARDUPILOT_DEFAULT_HOME_LON,
    ARDUPILOT_HEARTBEAT_TIMEOUT,
    ARDUPILOT_MODE_AUTO,
    ARDUPILOT_MODE_GUIDED,
    ARDUPILOT_MODE_LAND,
    ARDUPILOT_MODE_LOITER,
    ARDUPILOT_MODE_QLAND,
    ARDUPILOT_MODE_QLOITER,
    ARDUPILOT_MODE_RTL,
    ARDUPILOT_TELEMETRY_HZ,
    ARDUPILOT_VIDEO_SOURCE,
)
from schemas import AdapterBootstrapStatus, LatLon, TelemetrySnapshot

from .base import FlightControllerAdapter, VideoFrame


logger = logging.getLogger("arrakis.adapter.ardupilot")


def _distance_m(a: LatLon, b: LatLon) -> float:
    lat_scale = 111_320.0
    lon_scale = math.cos(math.radians(a.lat)) * 111_320.0
    dx = (b.lon - a.lon) * lon_scale
    dy = (b.lat - a.lat) * lat_scale
    return math.hypot(dx, dy)


def _project_point_from_home(home: LatLon, reference: LatLon, distance_m: float) -> LatLon:
    lat_scale = 111_320.0
    lon_scale = math.cos(math.radians(home.lat)) * 111_320.0
    dx = (reference.lon - home.lon) * lon_scale
    dy = (reference.lat - home.lat) * lat_scale
    norm = math.hypot(dx, dy)
    if norm < 1.0:
        dx = distance_m
        dy = 0.0
        norm = distance_m
    scale = distance_m / norm
    return LatLon(
        lat=home.lat + (dy * scale) / lat_scale,
        lon=home.lon + (dx * scale) / lon_scale,
    )


def _age_seconds(timestamp: float | None, now: float | None = None) -> float | None:
    if timestamp is None:
        return None
    return max((now or time.time()) - timestamp, 0.0)


def _bootstrap_wait_reason(target: str, timestamp: float | None, now: float | None = None) -> str:
    age = _age_seconds(timestamp, now)
    if age is None:
        return f"waiting for {target} (never received)"
    return f"waiting for {target} (last update {age:.1f}s ago)"


@dataclass
class _State:
    lat: float
    lon: float
    alt_m: float = 0.0
    airspeed_mps: float = 0.0
    groundspeed_mps: float = 0.0
    battery_percent: float = 100.0
    armed: bool = False
    flight_mode: str = "DISCONNECTED"
    vtol_state: str = "MC"
    mission_index: int = -1
    geofence_breached: bool = False
    sim_rtf: float = 1.0
    mode_valid: bool = False
    position_valid: bool = False
    gps_sensor_valid: bool = False
    gps_fix_type: int = 0
    gps_satellites: int = 0
    home_valid: bool = False


class ArduPilotAdapter(FlightControllerAdapter):
    """Real ArduPilot SITL adapter.

    The first concrete implementation uses pymavlink for VTOL control and
    OpenCV for adapter-owned video ingestion. The Arrakis core only sees the
    adapter contract exposed in base.py.
    """

    def __init__(self, profile: AirframeProfile) -> None:
        self._profile = profile
        self._connection = ARDUPILOT_CONNECTION
        self._video_source = ARDUPILOT_VIDEO_SOURCE
        self._heartbeat_timeout = ARDUPILOT_HEARTBEAT_TIMEOUT
        self._command_timeout = ARDUPILOT_COMMAND_TIMEOUT
        self._telemetry_hz = max(ARDUPILOT_TELEMETRY_HZ, 1.0)
        self._home = LatLon(lat=ARDUPILOT_DEFAULT_HOME_LAT, lon=ARDUPILOT_DEFAULT_HOME_LON)
        self._state = _State(lat=self._home.lat, lon=self._home.lon)
        self._telemetry_callbacks: list[Callable[[TelemetrySnapshot], None]] = []
        self._video_callbacks: list[Callable[[VideoFrame], None]] = []
        self._state_lock = threading.RLock()
        self._io_lock = threading.RLock()
        self._running = False
        self._telemetry_thread: threading.Thread | None = None
        self._video_thread: threading.Thread | None = None
        self._master: Any | None = None
        self._mavutil: Any | None = None
        self._cv2: Any | None = None
        self._capture: Any | None = None
        self._last_video_ts = 0.0
        self._outbound_count = 0
        self._return_count = 0
        self._route_leg = "idle"
        self._mission_seq_outbound_start = 0
        self._mission_seq_return_start = 0
        self._mission_seq_landing_start = 0
        self._mission_seq_end = 0
        self._mission_seq_takeoff = 0
        self._target_component = 1
        self._target_system = 1
        self._last_statustext: str | None = None
        self._pending_acks: dict[int, tuple[int, float]] = {}  # Fix 2: command → (result, timestamp)
        self._home_initialized = False
        self._heartbeat_received = False
        self._last_telemetry_at: float | None = None
        self._last_heartbeat_at: float | None = None
        self._last_mode_at: float | None = None
        self._last_position_at: float | None = None
        self._last_home_at: float | None = None
        # Fix 9: monotonic timestamps for freshness (immune to NTP clock jumps)
        self._last_telemetry_mono: float | None = None
        self._last_heartbeat_mono: float | None = None
        self._last_gps_sensor_mono: float | None = None
        # Fix 1+3: heartbeat watchdog and connection loss detection
        self._heartbeat_watchdog_timeout_s = max(self._heartbeat_timeout, 10.0)
        self._connection_lost = False
        self._consecutive_empty_reads = 0
        _MAX_CONSECUTIVE_EMPTY = 50  # ~10s at 0.2s timeout
        self._max_consecutive_empty = _MAX_CONSECUTIVE_EMPTY
        # Fix 8: pre-arm error collection
        self._prearm_errors: list[str] = []
        logger.info("ArduPilotAdapter initialized connection=%s video_source=%s", self._connection, self._video_source)

    def connect(self) -> None:
        if self._running and self._master is not None:
            logger.info("connect() called while already connected")
            return
        self._load_dependencies()
        logger.info("Connecting to ArduPilot via %s", self._connection)
        master = self._mavutil.mavlink_connection(
            self._connection,
            autoreconnect=True,
            source_system=255,
            source_component=190,
        )
        try:
            heartbeat = master.wait_heartbeat(timeout=self._heartbeat_timeout)
        except Exception as exc:
            raise RuntimeError(
                f"Timed out waiting for ArduPilot heartbeat on {self._connection} after {self._heartbeat_timeout:.1f}s"
            ) from exc
        if heartbeat is None:
            raise RuntimeError(
                f"Did not receive a valid ArduPilot heartbeat on {self._connection} within {self._heartbeat_timeout:.1f}s"
            )
        self._master = master
        self._target_system = master.target_system or 1
        self._target_component = master.target_component or 1
        self._handle_message(heartbeat)
        self._request_data_streams()
        self._running = True
        self._telemetry_thread = threading.Thread(target=self._telemetry_loop, name="arrakis-ardupilot-telemetry", daemon=True)
        self._telemetry_thread.start()
        if self._video_source:
            self._video_thread = threading.Thread(target=self._video_loop, name="arrakis-ardupilot-video", daemon=True)
            self._video_thread.start()
        logger.info(
            "ArduPilot heartbeat received system=%s component=%s",
            self._target_system,
            self._target_component,
        )

    def mission_execution_style(self) -> str:
        return "mission_oriented"

    def arm(self) -> None:
        self._prearm_errors.clear()  # Fix 8: collect fresh prearm errors
        pre_arm_mode = ARDUPILOT_MODE_QLOITER if self._profile.is_vtol else ARDUPILOT_MODE_LOITER
        self._set_mode(pre_arm_mode)
        self._send_command_with_retry(
            self._mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "arm/disarm command",
        )
        try:
            self._wait_for(lambda s: s.armed, "vehicle arm")
        except TimeoutError:
            # Fix 8: include prearm errors in exception message
            if self._prearm_errors:
                raise RuntimeError(
                    f"Arming failed. Pre-arm checks: {'; '.join(self._prearm_errors)}"
                ) from None
            raise

    def takeoff_multicopter(self, target_alt_m: float) -> None:
        baseline_alt_m = self.get_snapshot().alt_m
        self._set_mode(ARDUPILOT_MODE_GUIDED)
        self._send_command_with_retry(
            self._mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, target_alt_m],
            "takeoff command",
        )
        self._wait_for(
            lambda s: (s.alt_m - baseline_alt_m) >= target_alt_m * 0.7,
            f"takeoff climb {target_alt_m:.1f}m from baseline {baseline_alt_m:.1f}m",
        )

    def upload_roundtrip_mission(self, route_spec: dict[str, object]) -> None:
        outbound = [LatLon(**item) if isinstance(item, dict) else item for item in route_spec.get("outbound", [])]
        return_path = [LatLon(**item) if isinstance(item, dict) else item for item in route_spec.get("return_path", [])]
        home_raw = route_spec.get("home")
        home = LatLon(**home_raw) if isinstance(home_raw, dict) else home_raw
        takeoff_alt_m = float(route_spec.get("takeoff_alt_m", 40.0))
        cruise_alt_m = float(route_spec.get("cruise_alt_m", self._profile.altitudes.cruise_m))
        mission_points = outbound + return_path
        if not mission_points:
            raise ValueError("Roundtrip mission upload requires outbound and return_path points")
        self._upload_mission_points_mission_oriented(
            home=home or self._home,
            outbound=outbound,
            return_path=return_path,
            takeoff_alt_m=takeoff_alt_m,
            cruise_alt_m=cruise_alt_m,
        )
        self._outbound_count = len(outbound)
        self._return_count = len(return_path)
        self._route_leg = "takeoff"
        with self._state_lock:
            self._state.mission_index = self._mission_seq_takeoff

    def start_mission(self) -> None:
        self._set_mode(ARDUPILOT_MODE_AUTO)
        self._send_command_with_retry(
            self._mavutil.mavlink.MAV_CMD_MISSION_START,
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "mission start command",
        )

    def transition_to_fixedwing(self) -> None:
        self._send_command_with_retry(
            self._mavutil.mavlink.MAV_CMD_DO_VTOL_TRANSITION,
            [float(self._mavutil.mavlink.MAV_VTOL_STATE_FW), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "fixed-wing transition",
        )
        self._set_vtol_hint("FW")

    def prepare_multicopter_recovery(self, recovery_spec: dict[str, object]) -> None:
        logger.info("Preparing multicopter recovery spec=%s", recovery_spec)
        # Fix 4: unmask mode set failures — log warning instead of blind suppress
        try:
            self._set_mode(ARDUPILOT_MODE_LOITER)
        except Exception as exc:
            logger.warning("Failed to set LOITER mode during recovery prep: %s", exc)
            if self._profile.is_vtol:
                try:
                    self._set_mode(ARDUPILOT_MODE_QLOITER)
                except Exception as exc2:
                    logger.error("Failed to set QLOITER fallback during recovery prep: %s", exc2)

    def transition_to_multicopter(self) -> None:
        self._send_command_with_retry(
            self._mavutil.mavlink.MAV_CMD_DO_VTOL_TRANSITION,
            [float(self._mavutil.mavlink.MAV_VTOL_STATE_MC), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "multicopter transition",
        )
        self._set_vtol_hint("MC")
        # Fix 4: unmask mode set failure — log warning instead of blind suppress
        try:
            self._set_mode(ARDUPILOT_MODE_QLOITER)
        except Exception as exc:
            logger.warning("Post-transition QLOITER mode set failed: %s", exc)

    def return_to_home(self) -> None:
        self._set_mode(ARDUPILOT_MODE_RTL)
        self._route_leg = "return"

    def land_vertical(self) -> None:
        land_mode = ARDUPILOT_MODE_QLAND if self._profile.is_vtol else ARDUPILOT_MODE_LAND
        self._set_mode(land_mode)
        self._set_vtol_hint("MC")

    def abort(self, reason: str) -> None:
        # Fix 7: abort with retry and force disarm fallback
        logger.warning("Abort requested reason=%s", reason)
        for attempt in range(3):
            try:
                self.return_to_home()
                snapshot = self.get_snapshot()
                if snapshot.flight_mode.upper() in {"RTL", "QRTL", "LAND", "QLAND"}:
                    logger.info("Abort: vehicle entered safe mode=%s on attempt %d", snapshot.flight_mode, attempt + 1)
                    return
            except Exception as exc:
                logger.warning("Abort RTL attempt %d/3 failed: %s", attempt + 1, exc)
                time.sleep(0.5)
        # Last resort: force disarm
        logger.critical("Abort: RTL failed 3 times, attempting force disarm")
        try:
            self._send_command(
                self._mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                [0.0, 21196.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # force disarm magic number
            )
        except Exception as exc:
            logger.critical("Abort: force disarm also failed: %s", exc)

    def reset(self) -> None:
        logger.info("Resetting ArduPilot adapter state")
        self._outbound_count = 0
        self._return_count = 0
        self._route_leg = "idle"
        self._mission_seq_outbound_start = 0
        self._mission_seq_return_start = 0
        self._mission_seq_landing_start = 0
        self._mission_seq_end = 0
        self._mission_seq_takeoff = 0
        self._last_statustext = None
        self._pending_acks.clear()
        self._prearm_errors.clear()
        with self._state_lock:
            self._state.mission_index = -1
            self._state.geofence_breached = False
        if self._master is not None:
            with suppress(Exception):
                with self._io_lock:
                    self._master.mav.mission_clear_all_send(
                        self._target_system, self._target_component, 0,
                    )

    def get_snapshot(self) -> TelemetrySnapshot:
        with self._state_lock:
            state = self._state
            home = self._home
            # Fix 9: use monotonic clock for freshness (immune to NTP clock jumps)
            now_mono = time.monotonic()
            telemetry_fresh = bool(
                self._last_telemetry_mono is not None
                and (now_mono - self._last_telemetry_mono) <= max(2.5, 2.0 / self._telemetry_hz)
            )
        return TelemetrySnapshot(
            timestamp=time.time(),
            lat=state.lat,
            lon=state.lon,
            alt_m=state.alt_m,
            airspeed_mps=state.airspeed_mps,
            groundspeed_mps=state.groundspeed_mps,
            battery_percent=state.battery_percent,
            armed=state.armed,
            flight_mode=state.flight_mode,
            vtol_state=state.vtol_state,
            mission_index=state.mission_index,
            home_distance_m=_distance_m(home, LatLon(lat=state.lat, lon=state.lon))
            if state.position_valid and state.home_valid
            else float("inf"),
            geofence_breached=state.geofence_breached,
            sim_rtf=state.sim_rtf,
            telemetry_fresh=telemetry_fresh,
            mode_valid=state.mode_valid,
            position_valid=state.position_valid,
            gps_sensor_valid=bool(
                state.gps_sensor_valid
                and self._last_gps_sensor_mono is not None
                and (now_mono - self._last_gps_sensor_mono) <= 5.0
            ),
            gps_fix_type=state.gps_fix_type or None,
            gps_satellites=state.gps_satellites or None,
            home_valid=state.home_valid,
        )

    def current_leg(self) -> str:
        with self._state_lock:
            return self._route_leg

    def stream_telemetry(self, callback: Callable[[TelemetrySnapshot], None]) -> None:
        logger.info("Telemetry subscriber registered")
        self._telemetry_callbacks.append(callback)

    def stream_video(self, callback: Callable[[VideoFrame], None]) -> None:
        logger.info("Video subscriber registered")
        self._video_callbacks.append(callback)

    def get_home(self) -> LatLon:
        with self._state_lock:
            if not self._home_initialized and self._state.position_valid:
                return LatLon(lat=self._state.lat, lon=self._state.lon)
            return self._home

    def bootstrap_status(self) -> AdapterBootstrapStatus:
        snapshot = self.get_snapshot()
        now = time.time()
        connected = self._master is not None and self._heartbeat_received
        mission_ready = connected and snapshot.telemetry_fresh and snapshot.mode_valid and snapshot.position_valid and snapshot.home_valid
        telemetry_age_s = _age_seconds(self._last_telemetry_at, now)
        heartbeat_age_s = _age_seconds(self._last_heartbeat_at, now)
        mode_age_s = _age_seconds(self._last_mode_at, now)
        position_age_s = _age_seconds(self._last_position_at, now)
        home_age_s = _age_seconds(self._last_home_at, now)
        reason: str | None = None
        if not connected:
            reason = _bootstrap_wait_reason("heartbeat", self._last_heartbeat_at, now)
        elif not snapshot.telemetry_fresh:
            reason = _bootstrap_wait_reason("fresh telemetry", self._last_telemetry_at, now)
        elif not snapshot.mode_valid:
            reason = _bootstrap_wait_reason("valid flight mode", self._last_mode_at, now)
        elif not snapshot.position_valid:
            reason = _bootstrap_wait_reason("valid GPS position", self._last_position_at, now)
        elif not snapshot.home_valid:
            reason = _bootstrap_wait_reason("valid home position", self._last_home_at, now)
        return AdapterBootstrapStatus(
            connected=connected,
            heartbeat_received=self._heartbeat_received,
            telemetry_fresh=snapshot.telemetry_fresh,
            mode_ready=snapshot.mode_valid,
            position_ready=snapshot.position_valid,
            home_ready=snapshot.home_valid,
            mission_ready=mission_ready,
            last_telemetry_at=self._last_telemetry_at,
            last_heartbeat_at=self._last_heartbeat_at,
            last_mode_at=self._last_mode_at,
            last_position_at=self._last_position_at,
            last_home_at=self._last_home_at,
            telemetry_age_s=telemetry_age_s,
            heartbeat_age_s=heartbeat_age_s,
            mode_age_s=mode_age_s,
            position_age_s=position_age_s,
            home_age_s=home_age_s,
            reason=reason,
        )

    def _load_dependencies(self) -> None:
        if self._mavutil is None:
            try:
                self._mavutil = importlib.import_module("pymavlink.mavutil")
            except ModuleNotFoundError as exc:
                raise RuntimeError("pymavlink is required for ArduPilotAdapter") from exc
        if self._video_source and self._cv2 is None:
            try:
                self._cv2 = importlib.import_module("cv2")
            except ModuleNotFoundError as exc:
                raise RuntimeError("opencv-python is required for adapter-owned video streaming") from exc

    def _request_data_streams(self) -> None:
        if self._master is None:
            return
        logger.info("Requesting telemetry streams at %.1fHz", self._telemetry_hz)
        with self._io_lock:
            for stream_id in (
                self._mavutil.mavlink.MAV_DATA_STREAM_ALL,
                self._mavutil.mavlink.MAV_DATA_STREAM_POSITION,
                self._mavutil.mavlink.MAV_DATA_STREAM_EXTRA1,
                self._mavutil.mavlink.MAV_DATA_STREAM_EXTRA2,
                self._mavutil.mavlink.MAV_DATA_STREAM_EXTRA3,
            ):
                with suppress(Exception):
                    self._master.mav.request_data_stream_send(
                        self._target_system,
                        self._target_component,
                        stream_id,
                        int(self._telemetry_hz),
                        1,
                    )

    def _telemetry_loop(self) -> None:
        next_emit = 0.0
        while self._running and self._master is not None:
            msg = None
            # Fix 3: distinguish I/O errors from other exceptions
            with self._io_lock:
                try:
                    msg = self._master.recv_match(blocking=True, timeout=0.2)
                except (OSError, IOError) as exc:
                    logger.error("Connection I/O error in telemetry loop: %s", exc)
                    self._connection_lost = True
                    break
                except Exception as exc:
                    logger.warning("Unexpected recv_match error: %s", exc)
                    msg = None
            if msg is not None:
                self._consecutive_empty_reads = 0
                self._handle_message(msg)
            else:
                # Fix 3: track consecutive empty reads for connection loss detection
                self._consecutive_empty_reads += 1
                if self._consecutive_empty_reads >= self._max_consecutive_empty and not self._connection_lost:
                    logger.critical(
                        "Connection lost: %d consecutive empty reads (~%.1fs silence)",
                        self._consecutive_empty_reads,
                        self._consecutive_empty_reads * 0.2,
                    )
                    self._connection_lost = True
            # Fix 1: heartbeat watchdog — detect connection loss after connect()
            now_mono = time.monotonic()
            if self._last_heartbeat_mono is not None:
                heartbeat_age = now_mono - self._last_heartbeat_mono
                if heartbeat_age > self._heartbeat_watchdog_timeout_s and not self._connection_lost:
                    logger.critical(
                        "Heartbeat watchdog expired age=%.1fs threshold=%.1fs",
                        heartbeat_age,
                        self._heartbeat_watchdog_timeout_s,
                    )
                    self._connection_lost = True
            now = time.time()
            if now >= next_emit:
                snapshot = self.get_snapshot()
                for callback in list(self._telemetry_callbacks):
                    with suppress(Exception):
                        callback(snapshot)
                next_emit = now + (1.0 / self._telemetry_hz)

    def _video_loop(self) -> None:
        source = self._resolve_video_source(self._video_source)
        logger.info("Opening adapter video source=%s", source)
        capture = self._cv2.VideoCapture(source)
        if not capture.isOpened():
            logger.error("Failed to open adapter video source=%s", source)
            return
        self._capture = capture
        while self._running:
            started = time.time()
            ok, frame = capture.read()
            if not ok:
                time.sleep(0.05)
                continue
            now = time.time()
            fps = 0.0
            if self._last_video_ts:
                fps = 1.0 / max(now - self._last_video_ts, 1e-3)
            self._last_video_ts = now
            frame_obj = VideoFrame(
                timestamp=now,
                frame_bgr=frame,
                fps=fps,
                latency_ms=(time.time() - started) * 1000.0,
                metadata={},
            )
            for callback in list(self._video_callbacks):
                with suppress(Exception):
                    callback(frame_obj)
        capture.release()

    def _handle_message(self, msg: Any) -> None:
        msg_type = msg.get_type()
        if msg_type == "BAD_DATA":
            return
        now = time.time()
        now_mono = time.monotonic()  # Fix 9: monotonic parallel timestamp
        self._last_telemetry_at = now
        self._last_telemetry_mono = now_mono
        with self._state_lock:
            if msg_type == "HEARTBEAT":
                self._heartbeat_received = True
                self._last_heartbeat_at = now
                self._last_heartbeat_mono = now_mono  # Fix 9
                self._connection_lost = False  # Fix 1: clear connection loss on heartbeat
                self._consecutive_empty_reads = 0  # Fix 3: reset on heartbeat
                self._state.armed = bool(msg.base_mode & self._mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                self._state.flight_mode = self._mavutil.mode_string_v10(msg)
                self._state.mode_valid = self._state.flight_mode.upper() != "DISCONNECTED"
                if self._state.mode_valid:
                    self._last_mode_at = now
                self._refresh_route_leg_locked()
            elif msg_type == "GLOBAL_POSITION_INT":
                # Fix 10: validate GPS coordinates before accepting
                lat_raw = msg.lat / 1e7
                lon_raw = msg.lon / 1e7
                if (
                    -90.0 <= lat_raw <= 90.0
                    and -180.0 <= lon_raw <= 180.0
                    and not (lat_raw == 0.0 and lon_raw == 0.0)
                ):
                    self._state.lat = lat_raw
                    self._state.lon = lon_raw
                    self._state.alt_m = msg.relative_alt / 1000.0
                    self._state.position_valid = True
                    self._last_position_at = now
                    if not self._home_initialized:
                        self._home = LatLon(lat=self._state.lat, lon=self._state.lon)
                    if hasattr(msg, "vx") and hasattr(msg, "vy"):
                        self._state.groundspeed_mps = math.hypot(msg.vx, msg.vy) / 100.0
                else:
                    logger.warning("Rejecting invalid GPS position lat=%.7f lon=%.7f", lat_raw, lon_raw)
                    self._state.position_valid = False
            elif msg_type == "GPS_RAW_INT":
                self._last_gps_sensor_mono = now_mono
                fix_type = int(getattr(msg, "fix_type", 0))
                satellites = int(getattr(msg, "satellites_visible", 0))
                self._state.gps_sensor_valid = fix_type >= 3
                self._state.gps_fix_type = fix_type
                self._state.gps_satellites = max(satellites, 0)
            elif msg_type == "VFR_HUD":
                self._state.airspeed_mps = float(msg.airspeed)
                self._state.groundspeed_mps = float(msg.groundspeed)
            elif msg_type == "SYS_STATUS" and getattr(msg, "battery_remaining", -1) >= 0:
                self._state.battery_percent = float(msg.battery_remaining)
            elif msg_type == "MISSION_CURRENT":
                self._state.mission_index = int(msg.seq)
                self._refresh_route_leg_locked()
            elif msg_type == "HOME_POSITION":
                self._home = LatLon(lat=msg.latitude / 1e7, lon=msg.longitude / 1e7)
                self._home_initialized = True
                self._state.home_valid = True
                self._last_home_at = now
            elif msg_type == "NAMED_VALUE_FLOAT":
                name = msg.name.decode("utf-8", errors="ignore").strip("\x00")
                if name.upper() in {"RTF", "SIM_RTF"}:
                    self._state.sim_rtf = float(msg.value)
            elif msg_type == "COMMAND_ACK":
                # Fix 2: store ACKs by command ID (not single variable)
                command = int(getattr(msg, "command", -1))
                result = int(getattr(msg, "result", -1))
                self._pending_acks[command] = (result, time.time())
                logger.info("COMMAND_ACK command=%s result=%s", command, result)
        if msg_type == "STATUSTEXT":
            text = getattr(msg, "text", b"")
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="ignore")
            self._last_statustext = text.strip("\x00")
            # Fix 8: collect prearm errors for user-facing messages
            if "prearm" in self._last_statustext.lower():
                self._prearm_errors.append(self._last_statustext)
            logger.warning("STATUSTEXT severity=%s text=%s", getattr(msg, "severity", "?"), self._last_statustext)

    def _refresh_route_leg_locked(self) -> None:
        if self._outbound_count <= 0:
            self._route_leg = "idle"
            return
        mission_index = self._state.mission_index
        if mission_index >= self._mission_seq_end:
            self._route_leg = "idle"
        elif mission_index >= self._mission_seq_landing_start:
            self._route_leg = "landing"
        elif mission_index >= self._mission_seq_return_start:
            self._route_leg = "return"
        elif mission_index >= self._mission_seq_outbound_start:
            self._route_leg = "outbound"
        elif mission_index >= self._mission_seq_takeoff:
            self._route_leg = "takeoff"
        else:
            self._route_leg = "idle"

    def _set_mode(self, mode_name: str) -> None:
        master = self._require_master()
        with self._io_lock:
            mode_mapping = master.mode_mapping() or {}
            if mode_name not in mode_mapping:
                raise RuntimeError(f"Flight mode '{mode_name}' is not available on this ArduPilot target")
            master.set_mode(mode_mapping[mode_name])
        self._wait_for(
            lambda s: s.flight_mode.upper() == mode_name.upper(),
            f"mode {mode_name}",
        )

    # Fix 5: command retry with exponential backoff
    def _send_command_with_retry(
        self,
        command: int,
        params: list[float],
        description: str,
        retries: int = 3,
    ) -> None:
        """Send a MAVLink command with automatic retry on timeout.

        Uses exponential backoff (0.5s × attempt) between retries.
        Raises TimeoutError if all attempts fail.
        """
        last_exc: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                self._send_command(command, params)
                self._wait_for_command_ack(command, description)
                return
            except TimeoutError as exc:
                last_exc = exc
                logger.warning(
                    "Command %s attempt %d/%d timed out",
                    description,
                    attempt,
                    retries,
                )
                if attempt < retries:
                    time.sleep(0.5 * attempt)
        raise TimeoutError(
            f"{description} failed after {retries} attempts"
        ) from last_exc

    def _send_command(self, command: int, params: list[float]) -> None:
        master = self._require_master()
        # Fix 2: clear only this command's ACK entry (not all ACKs)
        with self._state_lock:
            self._pending_acks.pop(command, None)
        with self._io_lock:
            master.mav.command_long_send(
                self._target_system,
                self._target_component,
                command,
                0,
                *params,
            )

    def _upload_mission_points(self, points: list[LatLon]) -> None:
        master = self._require_master()
        with self._io_lock:
            master.mav.mission_clear_all_send(
                self._target_system, self._target_component, 0,
            )
            time.sleep(0.2)
            master.mav.mission_count_send(
                self._target_system, self._target_component, len(points), 0,
            )
            for _ in range(len(points)):
                request = self._recv_expected_locked({"MISSION_REQUEST", "MISSION_REQUEST_INT"}, self._command_timeout)
                seq = int(request.seq)
                point = points[seq]
                item = master.mav.mission_item_int_encode(
                    self._target_system,
                    self._target_component,
                    seq,
                    self._mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    self._mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                    0,
                    1,
                    0.0,
                    0.0,
                    0.0,
                    float("nan"),
                    int(point.lat * 1e7),
                    int(point.lon * 1e7),
                    float(self._profile.altitudes.cruise_m),
                )
                master.mav.send(item)
            ack = self._recv_expected_locked({"MISSION_ACK"}, self._command_timeout)
        result = getattr(ack, "type", None)
        accepted = self._mavutil.mavlink.MAV_MISSION_ACCEPTED
        if result not in (None, accepted):
            raise RuntimeError(f"Mission upload rejected with ack type={result}")

    def _upload_mission_points_mission_oriented(
        self,
        *,
        home: LatLon,
        outbound: list[LatLon],
        return_path: list[LatLon],
        takeoff_alt_m: float,
        cruise_alt_m: float,
    ) -> None:
        master = self._require_master()
        effective_return_path = list(return_path)
        if self._profile.is_vtol and effective_return_path:
            last_return = effective_return_path[-1]
            landing_distance = _distance_m(home, last_return)
            if landing_distance < self._profile.timing.vtol_landing_approach_min_m:
                adjusted = _project_point_from_home(home, last_return, self._profile.timing.vtol_landing_approach_min_m)
                logger.info(
                    "Adjusting final return waypoint for VTOL landing approach distance original=%.1fm adjusted=%.1fm",
                    landing_distance,
                    self._profile.timing.vtol_landing_approach_min_m,
                )
                effective_return_path[-1] = adjusted
        home_seq = 0
        takeoff_seq = 1
        outbound_start = 2
        return_start = outbound_start + len(outbound)
        landing_seq = return_start + len(effective_return_path)
        mission_items = [
            master.mav.mission_item_int_encode(
                self._target_system,
                self._target_component,
                home_seq,
                self._mavutil.mavlink.MAV_FRAME_GLOBAL,
                self._mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                0,
                1,
                0.0,
                0.0,
                0.0,
                float("nan"),
                int(home.lat * 1e7),
                int(home.lon * 1e7),
                0.0,
            ),
            master.mav.mission_item_int_encode(
                self._target_system,
                self._target_component,
                takeoff_seq,
                self._mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                self._mavutil.mavlink.MAV_CMD_NAV_VTOL_TAKEOFF if self._profile.is_vtol else self._mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,
                1,
                0.0,
                0.0,
                0.0,
                float("nan"),
                int(home.lat * 1e7),
                int(home.lon * 1e7),
                float(takeoff_alt_m),
            ),
        ]
        for offset, point in enumerate(outbound + effective_return_path, start=outbound_start):
            mission_items.append(
                master.mav.mission_item_int_encode(
                    self._target_system,
                    self._target_component,
                    offset,
                    self._mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    self._mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                    0,
                    1,
                    0.0,
                    0.0,
                    0.0,
                    float("nan"),
                    int(point.lat * 1e7),
                    int(point.lon * 1e7),
                    float(cruise_alt_m),
                )
            )
        mission_items.append(
            master.mav.mission_item_int_encode(
                self._target_system,
                self._target_component,
                landing_seq,
                self._mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                self._mavutil.mavlink.MAV_CMD_NAV_VTOL_LAND if self._profile.is_vtol else self._mavutil.mavlink.MAV_CMD_NAV_LAND,
                0,
                1,
                0.0,
                0.0,
                0.0,
                float("nan"),
                int(home.lat * 1e7),
                int(home.lon * 1e7),
                0.0,
            )
        )
        # Fix 6: total timeout for entire upload (prevents indefinite blocking)
        total_timeout = min(len(mission_items) * self._command_timeout, 120.0)
        upload_deadline = time.monotonic() + total_timeout
        with self._io_lock:
            master.mav.mission_clear_all_send(
                self._target_system, self._target_component, 0,
            )
            time.sleep(0.2)
            master.mav.mission_count_send(
                self._target_system, self._target_component, len(mission_items), 0,
            )
            for _ in range(len(mission_items)):
                remaining = upload_deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f"Mission upload total timeout ({total_timeout:.0f}s) exceeded "
                        f"after uploading some of {len(mission_items)} items"
                    )
                item_timeout = min(self._command_timeout, remaining)
                request = self._recv_expected_locked({"MISSION_REQUEST", "MISSION_REQUEST_INT"}, item_timeout)
                seq = int(request.seq)
                master.mav.send(mission_items[seq])
            remaining = upload_deadline - time.monotonic()
            ack_timeout = min(self._command_timeout, max(remaining, 1.0))
            ack = self._recv_expected_locked({"MISSION_ACK"}, ack_timeout)
            with suppress(Exception):
                master.waypoint_set_current_send(takeoff_seq)
            with suppress(Exception):
                self._log_uploaded_mission_locked(len(mission_items))
        result = getattr(ack, "type", None)
        accepted = self._mavutil.mavlink.MAV_MISSION_ACCEPTED
        if result not in (None, accepted):
            raise RuntimeError(f"Mission upload rejected with ack type={result}")
        logger.info(
            "Uploaded ArduPilot mission takeoff_seq=%s outbound_start=%s return_start=%s landing_start=%s count=%s",
            takeoff_seq,
            outbound_start,
            return_start,
            landing_seq,
            len(mission_items),
        )
        self._mission_seq_takeoff = takeoff_seq
        self._mission_seq_outbound_start = outbound_start
        self._mission_seq_return_start = return_start
        self._mission_seq_landing_start = landing_seq
        self._mission_seq_end = len(mission_items)

    def _log_uploaded_mission_locked(self, mission_count: int) -> None:
        master = self._require_master()
        master.waypoint_request_list_send()
        count_msg = self._recv_expected_locked({"MISSION_COUNT"}, self._command_timeout)
        vehicle_count = int(getattr(count_msg, "count", -1))
        commands: list[str] = []
        for seq in range(max(vehicle_count, 0)):
            master.waypoint_request_send(seq)
            item = self._recv_expected_locked({"MISSION_ITEM", "MISSION_ITEM_INT"}, self._command_timeout)
            command = int(getattr(item, "command", -1))
            frame = int(getattr(item, "frame", -1))
            if item.get_type() == "MISSION_ITEM_INT":
                alt = float(getattr(item, "z", 0.0))
            else:
                alt = float(getattr(item, "z", 0.0))
            commands.append(f"{seq}:{command}@frame{frame}:alt{alt:.1f}")
        logger.info(
            "Vehicle mission readback requested_count=%s vehicle_count=%s items=%s",
            mission_count,
            vehicle_count,
            commands,
        )

    def _recv_expected_locked(self, msg_types: set[str], timeout_seconds: float) -> Any:
        deadline = time.time() + timeout_seconds
        master = self._require_master()
        last_emit = 0.0
        while time.time() < deadline:
            msg = master.recv_match(blocking=True, timeout=0.5)
            if msg is None:
                continue
            self._handle_message(msg)
            # Emit telemetry callbacks while io_lock is held (RLock allows re-entry)
            # to prevent telemetry staleness during long mission uploads (C-2 fix)
            now = time.time()
            if now - last_emit >= 1.0 / self._telemetry_hz:
                snapshot = self.get_snapshot()
                for cb in list(self._telemetry_callbacks):
                    with suppress(Exception):
                        cb(snapshot)
                last_emit = now
            if msg.get_type() in msg_types:
                return msg
        raise TimeoutError(f"Timed out waiting for MAVLink message types={sorted(msg_types)}")

    def _wait_for(self, predicate: Callable[[TelemetrySnapshot], bool], description: str) -> None:
        deadline = time.time() + self._command_timeout
        while time.time() < deadline:
            snapshot = self.get_snapshot()
            if predicate(snapshot):
                return
            time.sleep(0.1)
        context = []
        if self._last_statustext:
            context.append(f"last_statustext={self._last_statustext}")
        # Fix 2: show recent pending ACKs for diagnostics
        with self._state_lock:
            if self._pending_acks:
                ack_summary = ", ".join(
                    f"cmd{cmd}=result{res}" for cmd, (res, _ts) in self._pending_acks.items()
                )
                context.append(f"pending_acks=[{ack_summary}]")
        context.append(f"flight_mode={self.get_snapshot().flight_mode}")
        raise TimeoutError(f"Timed out waiting for {description} ({', '.join(context)})")

    def _wait_for_command_ack(self, command: int, description: str) -> None:
        # Fix 2: read from per-command ACK dictionary instead of single variable
        deadline = time.time() + self._command_timeout
        while time.time() < deadline:
            with self._state_lock:
                ack = self._pending_acks.get(command)
            if ack is not None:
                result, _ack_time = ack
                accepted = self._mavutil.mavlink.MAV_RESULT_ACCEPTED
                in_progress = self._mavutil.mavlink.MAV_RESULT_IN_PROGRESS
                if result not in {accepted, in_progress}:
                    raise RuntimeError(
                        f"{description} rejected result={result} statustext={self._last_statustext or 'n/a'}"
                    )
                with self._state_lock:
                    self._pending_acks.pop(command, None)
                return
            time.sleep(0.05)
        raise TimeoutError(f"Timed out waiting for {description} ack statustext={self._last_statustext or 'n/a'}")

    def _set_vtol_hint(self, value: str) -> None:
        with self._state_lock:
            self._state.vtol_state = value

    def _require_master(self):
        if self._master is None:
            raise RuntimeError("ArduPilotAdapter is not connected")
        return self._master

    @staticmethod
    def _resolve_video_source(source: str | None) -> str | int:
        if source is None:
            return 0
        try:
            return int(source)
        except ValueError:
            return source
