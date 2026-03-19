"""Runtime concurrency regressions for ArduPilotAdapter.

These tests use a fake MAVLink transport to exercise the actual runtime
locking paths that previously broke around mission readback verification.
"""
from __future__ import annotations

import queue
import sys
import threading
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from airframe_profile import AirframeProfile
from flight_adapters.ardupilot import ArduPilotAdapter
from schemas import LatLon


class _FakeMessage:
    def __init__(self, msg_type: str, **fields) -> None:
        self._msg_type = msg_type
        for key, value in fields.items():
            setattr(self, key, value)

    def get_type(self) -> str:
        return self._msg_type


class _FakeMavlink:
    MAV_CMD_NAV_WAYPOINT = 16
    MAV_CMD_NAV_TAKEOFF = 22
    MAV_CMD_NAV_LAND = 21
    MAV_CMD_NAV_VTOL_TAKEOFF = 84
    MAV_CMD_NAV_VTOL_LAND = 85
    MAV_CMD_GET_HOME_POSITION = 410
    MAV_FRAME_GLOBAL = 0
    MAV_FRAME_GLOBAL_RELATIVE_ALT = 3
    MAV_MISSION_ACCEPTED = 0
    MAV_TYPE_GCS = 6
    MAV_AUTOPILOT_INVALID = 8
    MAV_MODE_FLAG_SAFETY_ARMED = 128


class _FakeMavutil:
    mavlink = _FakeMavlink()

    @staticmethod
    def mode_string_v10(msg) -> str:
        return getattr(msg, "flight_mode", "GUIDED")


class _FakeMav:
    def __init__(self, master: "_FakeMaster") -> None:
        self._master = master

    def mission_item_int_encode(
        self,
        target_system,
        target_component,
        seq,
        frame,
        command,
        current,
        autocontinue,
        param1,
        param2,
        param3,
        param4,
        x,
        y,
        z,
    ):
        return _FakeMessage(
            "MISSION_ITEM_INT",
            seq=seq,
            frame=frame,
            command=command,
            x=x,
            y=y,
            z=z,
        )

    def mission_clear_all_send(self, *args) -> None:
        self._master.sent.append(("mission_clear_all_send", args))

    def mission_count_send(self, *args) -> None:
        self._master.sent.append(("mission_count_send", args))

    def send(self, item) -> None:
        self._master.sent.append(("send", item.seq, item.command, item.frame, float(item.z)))

    def mission_request_list_send(self, *args) -> None:
        self._master.sent.append(("mission_request_list_send", args))
        self._master.readback_started.set()

    def mission_request_int_send(self, target_system, target_component, seq) -> None:
        self._master.sent.append(("mission_request_int_send", seq))

    def heartbeat_send(self, *args) -> None:
        self._master.sent.append(("heartbeat_send", args))

    def command_long_send(self, target_system, target_component, command, confirmation, *params) -> None:
        self._master.sent.append(("command_long_send", command, params))


class _FakeMaster:
    def __init__(self, messages: list[_FakeMessage]) -> None:
        self._messages: queue.Queue[_FakeMessage] = queue.Queue()
        for message in messages:
            self._messages.put(message)
        self.sent: list[tuple] = []
        self.readback_started = threading.Event()
        self.mav = _FakeMav(self)

    def recv_match(self, blocking: bool = True, timeout: float | None = None):
        try:
            message = self._messages.get(timeout=timeout if blocking else 0.0)
        except queue.Empty:
            return None
        # Give competing consumers a chance if the adapter ever releases the lock.
        time.sleep(0.01)
        return message

    def mode_mapping(self) -> dict[str, int]:
        return {"GUIDED": 4, "AUTO": 10, "QLOITER": 19}

    def close(self) -> None:
        return None


def _build_adapter(messages: list[_FakeMessage]) -> tuple[ArduPilotAdapter, _FakeMaster]:
    adapter = ArduPilotAdapter(AirframeProfile())
    master = _FakeMaster(messages)
    adapter._mavutil = _FakeMavutil()
    adapter._master = master
    adapter._target_system = 1
    adapter._target_component = 1
    adapter._command_timeout = 0.5
    adapter._telemetry_hz = 20.0
    return adapter, master


class TestArduPilotIoLockConcurrency:
    def test_mission_readback_not_stolen_by_competing_consumer(self):
        adapter, master = _build_adapter(
            [
                _FakeMessage("MISSION_REQUEST_INT", seq=0),
                _FakeMessage("MISSION_REQUEST_INT", seq=1),
                _FakeMessage("MISSION_REQUEST_INT", seq=2),
                _FakeMessage("MISSION_REQUEST_INT", seq=3),
                _FakeMessage("MISSION_REQUEST_INT", seq=4),
                _FakeMessage("MISSION_ACK", type=_FakeMavlink.MAV_MISSION_ACCEPTED),
                _FakeMessage("MISSION_COUNT", count=5),
                _FakeMessage(
                    "MISSION_ITEM_INT",
                    seq=0,
                    command=_FakeMavlink.MAV_CMD_NAV_WAYPOINT,
                    frame=_FakeMavlink.MAV_FRAME_GLOBAL,
                    z=125.0,
                ),
                _FakeMessage(
                    "MISSION_ITEM_INT",
                    seq=1,
                    command=_FakeMavlink.MAV_CMD_NAV_VTOL_TAKEOFF,
                    frame=_FakeMavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    z=20.0,
                ),
                _FakeMessage(
                    "MISSION_ITEM_INT",
                    seq=2,
                    command=_FakeMavlink.MAV_CMD_NAV_WAYPOINT,
                    frame=_FakeMavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    z=60.0,
                ),
                _FakeMessage(
                    "MISSION_ITEM_INT",
                    seq=3,
                    command=_FakeMavlink.MAV_CMD_NAV_WAYPOINT,
                    frame=_FakeMavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    z=60.0,
                ),
                _FakeMessage(
                    "MISSION_ITEM_INT",
                    seq=4,
                    command=_FakeMavlink.MAV_CMD_NAV_VTOL_LAND,
                    frame=_FakeMavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    z=0.0,
                ),
            ]
        )
        stolen_messages: list[str] = []
        stop_event = threading.Event()

        def _competing_consumer() -> None:
            assert master.readback_started.wait(1.0), "Readback phase never started"
            while not stop_event.is_set():
                acquired = adapter._io_lock.acquire(timeout=0.005)
                if not acquired:
                    continue
                try:
                    stolen = master.recv_match(blocking=True, timeout=0.005)
                    if stolen is not None:
                        stolen_messages.append(stolen.get_type())
                finally:
                    adapter._io_lock.release()
                time.sleep(0.001)

        rival = threading.Thread(target=_competing_consumer, daemon=True)
        rival.start()
        try:
            adapter._upload_mission_points_mission_oriented(
                home=LatLon(lat=37.5665, lon=126.9780),
                outbound=[LatLon(lat=37.5700, lon=126.9800)],
                return_path=[LatLon(lat=37.5665, lon=126.9780)],
                takeoff_alt_m=20.0,
                cruise_alt_m=60.0,
            )
        finally:
            stop_event.set()
            rival.join(timeout=1.0)

        assert master.readback_started.is_set(), "Mission readback should have been exercised"
        assert stolen_messages == [], f"Competing consumer stole mission messages: {stolen_messages}"
        assert adapter._mission_seq_end == 5

    def test_recv_expected_locked_allows_reentrant_bootstrap_callback(self):
        adapter, master = _build_adapter(
            [
                _FakeMessage(
                    "GLOBAL_POSITION_INT",
                    lat=int(37.5665 * 1e7),
                    lon=int(126.9780 * 1e7),
                    relative_alt=1500,
                    vx=0,
                    vy=0,
                ),
                _FakeMessage("MISSION_ACK", type=_FakeMavlink.MAV_MISSION_ACCEPTED),
            ]
        )
        adapter._heartbeat_received = True
        adapter._last_heartbeat_at = time.time()
        callback_results: list[bool] = []

        def _callback(_snapshot) -> None:
            bootstrap = adapter.bootstrap_status()
            adapter.get_snapshot()
            adapter.current_leg()
            callback_results.append(bootstrap.position_ready)

        adapter.stream_telemetry(_callback)

        with adapter._io_lock:
            message = adapter._recv_expected_locked({"MISSION_ACK"}, 0.5)

        assert message.get_type() == "MISSION_ACK"
        assert callback_results == [True]
        assert any(
            entry[0] == "command_long_send" and entry[1] == _FakeMavlink.MAV_CMD_GET_HOME_POSITION
            for entry in master.sent
        ), "bootstrap_status should be able to re-enter io_lock and request home position"
