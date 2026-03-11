from __future__ import annotations

import importlib
import logging
import math
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Callable

from config import (
    ARDUPILOT_COMMAND_TIMEOUT,
    ARDUPILOT_CONNECTION,
    ARDUPILOT_DEFAULT_HOME_LAT,
    ARDUPILOT_DEFAULT_HOME_LON,
    ARDUPILOT_HEARTBEAT_TIMEOUT,
    ARDUPILOT_MODE_AUTO,
    ARDUPILOT_MODE_GUIDED,
    ARDUPILOT_MODE_LOITER,
    ARDUPILOT_MODE_QLAND,
    ARDUPILOT_MODE_QLOITER,
    ARDUPILOT_MODE_RTL,
    ARDUPILOT_TELEMETRY_HZ,
    ARDUPILOT_VIDEO_SOURCE,
    CRUISE_ALT_M,
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
    home_valid: bool = False


class ArduPilotAdapter(FlightControllerAdapter):
    """Real ArduPilot SITL adapter.

    The first concrete implementation uses pymavlink for VTOL control and
    OpenCV for adapter-owned video ingestion. The Arrakis core only sees the
    adapter contract exposed in base.py.
    """

    def __init__(self) -> None:
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
        self._mission_seq_end = 0
        self._mission_seq_takeoff = 0
        self._target_component = 1
        self._target_system = 1
        self._last_statustext: str | None = None
        self._last_command_ack: tuple[int, int, float] | None = None
        self._home_initialized = False
        self._heartbeat_received = False
        self._last_telemetry_at: float | None = None
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
        self._set_mode(ARDUPILOT_MODE_QLOITER)
        self._send_command(
            self._mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
        self._wait_for_command_ack(self._mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, "arm/disarm command")
        self._wait_for(lambda s: s.armed, "vehicle arm")

    def takeoff_multicopter(self, target_alt_m: float) -> None:
        baseline_alt_m = self.get_snapshot().alt_m
        self._set_mode(ARDUPILOT_MODE_GUIDED)
        self._send_command(
            self._mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, target_alt_m],
        )
        self._wait_for_command_ack(self._mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, "takeoff command")
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
        cruise_alt_m = float(route_spec.get("cruise_alt_m", CRUISE_ALT_M))
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
        self._send_command(
            self._mavutil.mavlink.MAV_CMD_MISSION_START,
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
        self._wait_for_command_ack(self._mavutil.mavlink.MAV_CMD_MISSION_START, "mission start command")

    def transition_to_fixedwing(self) -> None:
        self._send_command(
            self._mavutil.mavlink.MAV_CMD_DO_VTOL_TRANSITION,
            [float(self._mavutil.mavlink.MAV_VTOL_STATE_FW), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
        self._wait_for_command_ack(self._mavutil.mavlink.MAV_CMD_DO_VTOL_TRANSITION, "fixed-wing transition")
        self._set_vtol_hint("FW")

    def prepare_multicopter_recovery(self, recovery_spec: dict[str, object]) -> None:
        logger.info("Preparing multicopter recovery spec=%s", recovery_spec)
        with suppress(Exception):
            self._set_mode(ARDUPILOT_MODE_LOITER)

    def transition_to_multicopter(self) -> None:
        self._send_command(
            self._mavutil.mavlink.MAV_CMD_DO_VTOL_TRANSITION,
            [float(self._mavutil.mavlink.MAV_VTOL_STATE_MC), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
        self._wait_for_command_ack(self._mavutil.mavlink.MAV_CMD_DO_VTOL_TRANSITION, "multicopter transition")
        self._set_vtol_hint("MC")
        with suppress(Exception):
            self._set_mode(ARDUPILOT_MODE_QLOITER)

    def return_to_home(self) -> None:
        self._set_mode(ARDUPILOT_MODE_RTL)
        self._route_leg = "return"

    def land_vertical(self) -> None:
        self._set_mode(ARDUPILOT_MODE_QLAND)
        self._set_vtol_hint("MC")

    def abort(self, reason: str) -> None:
        logger.warning("Abort requested reason=%s", reason)
        with suppress(Exception):
            self.return_to_home()

    def reset(self) -> None:
        logger.info("Resetting ArduPilot adapter state")
        self._outbound_count = 0
        self._return_count = 0
        self._route_leg = "idle"
        self._mission_seq_outbound_start = 0
        self._mission_seq_return_start = 0
        self._mission_seq_end = 0
        self._mission_seq_takeoff = 0
        self._last_statustext = None
        self._last_command_ack = None
        with self._state_lock:
            self._state.mission_index = -1
            self._state.geofence_breached = False
        if self._master is not None:
            with suppress(Exception):
                with self._io_lock:
                    self._master.waypoint_clear_all_send()

    def get_snapshot(self) -> TelemetrySnapshot:
        with self._state_lock:
            state = self._state
            home = self._home
            telemetry_fresh = bool(
                self._last_telemetry_at is not None
                and (time.time() - self._last_telemetry_at) <= max(2.5, 2.0 / self._telemetry_hz)
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
            else 0.0,
            geofence_breached=state.geofence_breached,
            sim_rtf=state.sim_rtf,
            telemetry_fresh=telemetry_fresh,
            mode_valid=state.mode_valid,
            position_valid=state.position_valid,
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
        connected = self._master is not None and self._heartbeat_received
        mission_ready = connected and snapshot.telemetry_fresh and snapshot.mode_valid and snapshot.position_valid and snapshot.home_valid
        reason: str | None = None
        if not connected:
            reason = "waiting for heartbeat"
        elif not snapshot.telemetry_fresh:
            reason = "waiting for fresh telemetry"
        elif not snapshot.mode_valid:
            reason = "waiting for valid flight mode"
        elif not snapshot.position_valid:
            reason = "waiting for valid GPS position"
        elif not snapshot.home_valid:
            reason = "waiting for valid home position"
        return AdapterBootstrapStatus(
            connected=connected,
            heartbeat_received=self._heartbeat_received,
            telemetry_fresh=snapshot.telemetry_fresh,
            mode_ready=snapshot.mode_valid,
            position_ready=snapshot.position_valid,
            home_ready=snapshot.home_valid,
            mission_ready=mission_ready,
            last_telemetry_at=self._last_telemetry_at,
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
            with self._io_lock:
                with suppress(Exception):
                    msg = self._master.recv_match(blocking=True, timeout=0.2)
            if msg is not None:
                self._handle_message(msg)
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
        self._last_telemetry_at = time.time()
        with self._state_lock:
            if msg_type == "HEARTBEAT":
                self._heartbeat_received = True
                self._state.armed = bool(msg.base_mode & self._mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                self._state.flight_mode = self._mavutil.mode_string_v10(msg)
                self._state.mode_valid = self._state.flight_mode.upper() != "DISCONNECTED"
                self._refresh_route_leg_locked()
            elif msg_type == "GLOBAL_POSITION_INT":
                self._state.lat = msg.lat / 1e7
                self._state.lon = msg.lon / 1e7
                self._state.alt_m = msg.relative_alt / 1000.0
                self._state.position_valid = bool(msg.lat or msg.lon)
                if not self._home_initialized:
                    self._home = LatLon(lat=self._state.lat, lon=self._state.lon)
                    self._state.home_valid = self._state.position_valid
                if hasattr(msg, "vx") and hasattr(msg, "vy"):
                    self._state.groundspeed_mps = math.hypot(msg.vx, msg.vy) / 100.0
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
            elif msg_type == "NAMED_VALUE_FLOAT":
                name = msg.name.decode("utf-8", errors="ignore").strip("\x00")
                if name.upper() in {"RTF", "SIM_RTF"}:
                    self._state.sim_rtf = float(msg.value)
        if msg_type == "COMMAND_ACK":
            command = int(getattr(msg, "command", -1))
            result = int(getattr(msg, "result", -1))
            self._last_command_ack = (command, result, time.time())
            logger.info("COMMAND_ACK command=%s result=%s", command, result)
        elif msg_type == "STATUSTEXT":
            text = getattr(msg, "text", b"")
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="ignore")
            self._last_statustext = text.strip("\x00")
            logger.warning("STATUSTEXT severity=%s text=%s", getattr(msg, "severity", "?"), self._last_statustext)

    def _refresh_route_leg_locked(self) -> None:
        if self._outbound_count <= 0:
            self._route_leg = "idle"
            return
        mission_index = self._state.mission_index
        flight_mode = self._state.flight_mode.upper()
        if mission_index >= self._mission_seq_end:
            self._route_leg = "idle"
        elif mission_index >= self._mission_seq_end - 1 and flight_mode in {
            ARDUPILOT_MODE_RTL.upper(),
            ARDUPILOT_MODE_QLOITER.upper(),
            ARDUPILOT_MODE_QLAND.upper(),
        }:
            self._route_leg = "idle"
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

    def _send_command(self, command: int, params: list[float]) -> None:
        master = self._require_master()
        self._last_command_ack = None
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
            master.waypoint_clear_all_send()
            time.sleep(0.2)
            master.waypoint_count_send(len(points))
            for _ in range(len(points)):
                request = self._recv_expected_locked({"MISSION_REQUEST", "MISSION_REQUEST_INT"}, self._command_timeout)
                seq = int(request.seq)
                point = points[seq]
                item = master.mav.mission_item_int_encode(
                    self._target_system,
                    self._target_component,
                    seq,
                    self._mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                    self._mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                    0,
                    1,
                    0.0,
                    0.0,
                    0.0,
                    float("nan"),
                    int(point.lat * 1e7),
                    int(point.lon * 1e7),
                    float(CRUISE_ALT_M),
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
        home_seq = 0
        takeoff_seq = 1
        outbound_start = 2
        return_start = outbound_start + len(outbound)
        mission_items = [
            master.mav.mission_item_int_encode(
                self._target_system,
                self._target_component,
                home_seq,
                self._mavutil.mavlink.MAV_FRAME_GLOBAL_INT,
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
                self._mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                self._mavutil.mavlink.MAV_CMD_NAV_VTOL_TAKEOFF,
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
        for offset, point in enumerate(outbound + return_path, start=outbound_start):
            mission_items.append(
                master.mav.mission_item_int_encode(
                    self._target_system,
                    self._target_component,
                    offset,
                    self._mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
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
        with self._io_lock:
            master.waypoint_clear_all_send()
            time.sleep(0.2)
            master.waypoint_count_send(len(mission_items))
            for _ in range(len(mission_items)):
                request = self._recv_expected_locked({"MISSION_REQUEST", "MISSION_REQUEST_INT"}, self._command_timeout)
                seq = int(request.seq)
                master.mav.send(mission_items[seq])
            ack = self._recv_expected_locked({"MISSION_ACK"}, self._command_timeout)
            with suppress(Exception):
                master.waypoint_set_current_send(takeoff_seq)
            with suppress(Exception):
                self._log_uploaded_mission_locked(len(mission_items))
        result = getattr(ack, "type", None)
        accepted = self._mavutil.mavlink.MAV_MISSION_ACCEPTED
        if result not in (None, accepted):
            raise RuntimeError(f"Mission upload rejected with ack type={result}")
        logger.info(
            "Uploaded ArduPilot mission takeoff_seq=%s outbound_start=%s return_start=%s count=%s",
            takeoff_seq,
            outbound_start,
            return_start,
            len(mission_items),
        )
        self._mission_seq_takeoff = takeoff_seq
        self._mission_seq_outbound_start = outbound_start
        self._mission_seq_return_start = return_start
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
        while time.time() < deadline:
            msg = master.recv_match(blocking=True, timeout=0.5)
            if msg is None:
                continue
            self._handle_message(msg)
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
        if self._last_command_ack:
            command, result, _ = self._last_command_ack
            context.append(f"last_command_ack=({command},{result})")
        context.append(f"flight_mode={self.get_snapshot().flight_mode}")
        raise TimeoutError(f"Timed out waiting for {description} ({', '.join(context)})")

    def _wait_for_command_ack(self, command: int, description: str) -> None:
        deadline = time.time() + self._command_timeout
        while time.time() < deadline:
            ack = self._last_command_ack
            if ack is not None and ack[0] == command:
                result = ack[1]
                accepted = self._mavutil.mavlink.MAV_RESULT_ACCEPTED
                in_progress = self._mavutil.mavlink.MAV_RESULT_IN_PROGRESS
                if result not in {accepted, in_progress}:
                    raise RuntimeError(
                        f"{description} rejected result={result} statustext={self._last_statustext or 'n/a'}"
                    )
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
