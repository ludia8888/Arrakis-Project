from __future__ import annotations

import time
import threading

from config import (
    BATTERY_RTL_THRESHOLD,
    FALLBACK_RECOVERY,
    LOITER_RADIUS_M,
    PRIMARY_RECOVERY,
    RECOVERY_ALT_M,
    TAKEOFF_ALT_M,
)
from flight_adapters.base import FlightControllerAdapter, VideoFrame
from schemas import RoutePreview, TelemetrySnapshot

from .mission_state_machine import MissionStateMachine
from .telemetry_hub import TelemetryHub


class ArrakisController:
    def __init__(self, adapter: FlightControllerAdapter) -> None:
        self.adapter = adapter
        self.state_machine = MissionStateMachine()
        self._mission_thread: threading.Thread | None = None

        self.adapter.connect()
        self.telemetry_hub = TelemetryHub(self.adapter.get_snapshot())
        self.adapter.stream_telemetry(self._on_telemetry)
        self.adapter.stream_video(self._on_video)

    def set_route(self, preview: RoutePreview) -> RoutePreview:
        return self.state_machine.set_route(preview, self._mission_thread is not None and self._mission_thread.is_alive())

    def start_mission(self) -> None:
        self.state_machine.start_mission(self._mission_thread is not None and self._mission_thread.is_alive())
        self._mission_thread = threading.Thread(target=self._run_mission, daemon=True)
        self._mission_thread.start()

    def abort(self, reason: str = "manual operator abort") -> None:
        self.state_machine.abort("ABORT_MANUAL", reason)
        self.adapter.abort(reason)

    def rtl(self) -> None:
        self.state_machine.abort("RTL_BATTERY", "manual rtl requested")
        self.adapter.return_to_home()

    def reset(self) -> None:
        self.adapter.reset()
        self.telemetry_hub.reset(self.adapter.get_snapshot())
        self.state_machine.reset()

    def state_payload(self):
        status = self.state_machine.snapshot()
        current_leg = self.adapter.current_leg() if hasattr(self.adapter, "current_leg") else "idle"
        return self.telemetry_hub.state_payload(
            mission_phase=status.phase,
            abort_reason=status.abort_reason,
            route_preview=status.route_preview,
            current_leg=current_leg,
        )

    def latest_jpeg(self) -> bytes:
        return self.telemetry_hub.latest_jpeg()

    def _on_telemetry(self, snapshot: TelemetrySnapshot) -> None:
        route_preview = self.state_machine.route_preview
        decision = self.telemetry_hub.on_telemetry(snapshot, route_preview)
        phase = self.state_machine.phase
        if decision.trigger_battery_rtl and phase not in {"RTL_BATTERY", "LANDING", "COMPLETE"}:
            self.state_machine.abort("RTL_BATTERY", "battery threshold reached")
            self.adapter.return_to_home()
        if decision.trigger_geofence_abort and phase not in {"ABORT_GEOFENCE", "LANDING", "COMPLETE"}:
            self.state_machine.abort("ABORT_GEOFENCE", "route-derived geofence breached")
            self.adapter.abort("geofence breach")

    def _on_video(self, frame: VideoFrame) -> None:
        self.telemetry_hub.on_video(frame)

    def _run_mission(self) -> None:
        route_preview = self.state_machine.require_route()
        self.state_machine.mark_phase("ARMING")
        self.adapter.arm()
        time.sleep(1.0)

        self.state_machine.mark_phase("TAKEOFF_MC")
        self.adapter.takeoff_multicopter(TAKEOFF_ALT_M)
        time.sleep(1.0)

        self.state_machine.mark_phase("TRANSITION_FW")
        self.adapter.transition_to_fixedwing()
        self.adapter.upload_roundtrip_mission(
            {
                "outbound": [point.model_dump() for point in route_preview.outbound],
                "return_path": [point.model_dump() for point in route_preview.return_path],
                "geofence": [point.model_dump() for point in route_preview.geofence.coordinates],
            }
        )
        self.adapter.start_mission()
        self.state_machine.mark_phase("OUTBOUND")

        # Track outbound/return and trigger recovery near the end.
        while True:
            state = self.state_payload()
            if state.mission_phase in {"ABORT_GEOFENCE", "RTL_BATTERY", "ABORT_MANUAL"}:
                return
            if state.route_progress.current_leg == "return":
                self.state_machine.mark_phase("RETURN")
            if state.route_progress.current_leg == "idle" and state.telemetry.home_distance_m <= 120:
                break
            time.sleep(0.2)

        self.state_machine.mark_phase("PRE_MC_RECOVERY")
        self.adapter.prepare_multicopter_recovery(
            {
                "recovery_center": route_preview.home.model_dump(),
                "target_alt_m": RECOVERY_ALT_M,
                "loiter_radius_m": LOITER_RADIUS_M,
            }
        )
        if not self._wait_for_recovery(PRIMARY_RECOVERY, False):
            if self.state_machine.abort_reason:
                return
            self.adapter.return_to_home()
            if not self._wait_for_recovery(FALLBACK_RECOVERY, True):
                self.state_machine.abort("ABORT_MANUAL", "operator intervention required after recovery fallback")
                return

        self.state_machine.mark_phase("TRANSITION_MC")
        self.adapter.transition_to_multicopter()
        time.sleep(1.0)
        self.state_machine.mark_phase("LANDING")
        self.adapter.land_vertical()

        while True:
            telemetry = self.telemetry_hub.telemetry_snapshot()
            if not telemetry.armed or telemetry.alt_m <= 0.5:
                break
            time.sleep(0.2)
        self.state_machine.complete()

    def _wait_for_recovery(self, thresholds, fallback: bool) -> bool:
        deadline = time.time() + thresholds.timeout_seconds
        stable_since: float | None = None
        while time.time() < deadline:
            telemetry = self.telemetry_hub.telemetry_snapshot()
            if telemetry.geofence_breached:
                self.state_machine.abort("ABORT_GEOFENCE", "route-derived geofence breached")
                return False
            if telemetry.battery_percent <= BATTERY_RTL_THRESHOLD:
                self.state_machine.abort("RTL_BATTERY", "battery threshold reached")
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
