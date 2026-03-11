from __future__ import annotations

import threading
import time

from config import (
    BATTERY_RTL_THRESHOLD,
    FALLBACK_RECOVERY,
    LOITER_RADIUS_M,
    PRIMARY_RECOVERY,
    RECOVERY_ALT_M,
    TAKEOFF_ALT_M,
)
from flight_adapters.base import FlightControllerAdapter

from .mission_state_machine import INTERRUPT_PHASES, MissionStateMachine
from .telemetry_hub import TelemetryHub


class MissionExecutor:
    def __init__(
        self,
        *,
        adapter: FlightControllerAdapter,
        state_machine: MissionStateMachine,
        telemetry_hub: TelemetryHub,
    ) -> None:
        self.adapter = adapter
        self.state_machine = state_machine
        self.telemetry_hub = telemetry_hub

    def run_roundtrip_mission(self, cancel_event: threading.Event) -> None:
        route_preview = self.state_machine.require_route()
        if cancel_event.is_set():
            return
        self.state_machine.mark_phase("ARMING")
        self.adapter.arm()
        if self._sleep_with_cancel(cancel_event, 1.0):
            return

        self.state_machine.mark_phase("TAKEOFF_MC")
        self.adapter.takeoff_multicopter(TAKEOFF_ALT_M)
        if self._sleep_with_cancel(cancel_event, 1.0):
            return

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

        while True:
            if cancel_event.is_set() or self.state_machine.phase in INTERRUPT_PHASES:
                return
            current_leg = self.adapter.current_leg()
            telemetry = self.telemetry_hub.telemetry_snapshot()
            if current_leg == "return":
                self.state_machine.mark_phase("RETURN")
            if current_leg == "idle" and telemetry.home_distance_m <= 120:
                break
            if self._sleep_with_cancel(cancel_event, 0.2):
                return

        self.state_machine.mark_phase("PRE_MC_RECOVERY")
        self.adapter.prepare_multicopter_recovery(
            {
                "recovery_center": route_preview.home.model_dump(),
                "target_alt_m": RECOVERY_ALT_M,
                "loiter_radius_m": LOITER_RADIUS_M,
            }
        )
        if not self._wait_for_recovery(PRIMARY_RECOVERY, cancel_event):
            if self.state_machine.abort_reason:
                return
            if cancel_event.is_set():
                return
            self.adapter.return_to_home()
            if not self._wait_for_recovery(FALLBACK_RECOVERY, cancel_event):
                if cancel_event.is_set():
                    return
                self.state_machine.abort("ABORT_MANUAL", "operator intervention required after recovery fallback")
                return

        self.state_machine.mark_phase("TRANSITION_MC")
        self.adapter.transition_to_multicopter()
        if self._sleep_with_cancel(cancel_event, 1.0):
            return
        self.state_machine.mark_phase("LANDING")
        self.adapter.land_vertical()

        while True:
            if cancel_event.is_set():
                return
            telemetry = self.telemetry_hub.telemetry_snapshot()
            if not telemetry.armed or telemetry.alt_m <= 0.5:
                break
            if self._sleep_with_cancel(cancel_event, 0.2):
                return
        self.state_machine.complete()

    def _wait_for_recovery(self, thresholds, cancel_event: threading.Event) -> bool:
        deadline = time.time() + thresholds.timeout_seconds
        stable_since: float | None = None
        while time.time() < deadline:
            if cancel_event.is_set():
                return False
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
            if self._sleep_with_cancel(cancel_event, 0.2):
                return False
        return False

    def _sleep_with_cancel(self, cancel_event: threading.Event, duration_seconds: float, step_seconds: float = 0.1) -> bool:
        deadline = time.time() + duration_seconds
        while time.time() < deadline:
            if cancel_event.is_set():
                return True
            time.sleep(min(step_seconds, max(0.0, deadline - time.time())))
        return cancel_event.is_set()
