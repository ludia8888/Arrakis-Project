from __future__ import annotations

import logging
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


logger = logging.getLogger("arrakis.executor")


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
            logger.info("Mission cancelled before start")
            return
        self.state_machine.mark_phase("ARMING", reason="mission executor started arming sequence")
        self.adapter.arm()
        if self._sleep_with_cancel(cancel_event, 1.0):
            logger.info("Mission cancelled during ARMING")
            return

        self.state_machine.mark_phase("TAKEOFF_MC", reason="arm complete, takeoff requested")
        self.adapter.takeoff_multicopter(TAKEOFF_ALT_M)
        if self._sleep_with_cancel(cancel_event, 1.0):
            logger.info("Mission cancelled during TAKEOFF_MC")
            return

        self.state_machine.mark_phase("TRANSITION_FW", reason="takeoff complete, switching to fixed-wing")
        self.adapter.transition_to_fixedwing()
        self.adapter.upload_roundtrip_mission(
            {
                "outbound": [point.model_dump() for point in route_preview.outbound],
                "return_path": [point.model_dump() for point in route_preview.return_path],
                "geofence": [point.model_dump() for point in route_preview.geofence.coordinates],
            },
        )
        self.adapter.start_mission()
        self.state_machine.mark_phase("OUTBOUND", reason="mission uploaded and started")
        logger.info("Entered OUTBOUND")

        while True:
            if cancel_event.is_set() or self.state_machine.phase in INTERRUPT_PHASES:
                logger.info("Mission interrupted during outbound/return loop phase=%s", self.state_machine.phase)
                return
            current_leg = self.adapter.current_leg()
            telemetry = self.telemetry_hub.telemetry_snapshot()
            if current_leg == "return":
                self.state_machine.mark_phase("RETURN", reason="adapter reported return leg")
                logger.info("Leg transitioned to RETURN")
            if current_leg == "idle" and telemetry.home_distance_m <= 120:
                break
            if self._sleep_with_cancel(cancel_event, 0.2):
                logger.info("Mission cancelled during route progression")
                return

        self.state_machine.mark_phase("PRE_MC_RECOVERY", reason="route complete, preparing multicopter recovery")
        logger.info("Entered PRE_MC_RECOVERY")
        self.adapter.prepare_multicopter_recovery(
            {
                "recovery_center": route_preview.home.model_dump(),
                "target_alt_m": RECOVERY_ALT_M,
                "loiter_radius_m": LOITER_RADIUS_M,
            },
        )
        if not self._wait_for_recovery(PRIMARY_RECOVERY, cancel_event):
            if self.state_machine.abort_reason:
                logger.warning("Primary recovery ended due to abort reason=%s", self.state_machine.abort_reason)
                return
            if cancel_event.is_set():
                logger.info("Mission cancelled during primary recovery")
                return
            logger.warning("Primary recovery timed out, attempting fallback recovery")
            self.adapter.return_to_home()
            if not self._wait_for_recovery(FALLBACK_RECOVERY, cancel_event):
                if cancel_event.is_set():
                    logger.info("Mission cancelled during fallback recovery")
                    return
                self.state_machine.abort("ABORT_MANUAL", "operator intervention required after recovery fallback")
                logger.error("Fallback recovery failed, operator intervention required")
                return

        self.state_machine.mark_phase("TRANSITION_MC", reason="recovery thresholds satisfied")
        self.adapter.transition_to_multicopter()
        if self._sleep_with_cancel(cancel_event, 1.0):
            logger.info("Mission cancelled during TRANSITION_MC")
            return
        self.state_machine.mark_phase("LANDING", reason="multicopter transition complete, vertical landing requested")
        self.adapter.land_vertical()

        while True:
            if cancel_event.is_set():
                logger.info("Mission cancelled during LANDING")
                return
            telemetry = self.telemetry_hub.telemetry_snapshot()
            if not telemetry.armed or telemetry.alt_m <= 0.5:
                break
            if self._sleep_with_cancel(cancel_event, 0.2):
                logger.info("Mission cancelled while waiting for landing")
                return
        self.state_machine.complete()
        logger.info("Mission reached COMPLETE")

    def _wait_for_recovery(self, thresholds, cancel_event: threading.Event) -> bool:
        deadline = time.time() + thresholds.timeout_seconds
        stable_since: float | None = None
        while time.time() < deadline:
            if cancel_event.is_set():
                logger.info("Recovery wait cancelled")
                return False
            telemetry = self.telemetry_hub.telemetry_snapshot()
            if telemetry.geofence_breached:
                self.state_machine.abort("ABORT_GEOFENCE", "route-derived geofence breached")
                logger.warning("Recovery failed due to geofence breach")
                return False
            if telemetry.battery_percent <= BATTERY_RTL_THRESHOLD:
                self.state_machine.abort("RTL_BATTERY", "battery threshold reached")
                logger.warning("Recovery failed due to battery threshold at %.1f%%", telemetry.battery_percent)
                return False
            conditions_met = (
                telemetry.airspeed_mps <= thresholds.speed_threshold_mps
                and telemetry.home_distance_m <= thresholds.home_distance_threshold_m
                and abs(telemetry.alt_m - RECOVERY_ALT_M) <= thresholds.altitude_deviation_m
            )
            if conditions_met:
                stable_since = stable_since or time.time()
                if time.time() - stable_since >= thresholds.dwell_seconds:
                    logger.info(
                        "Recovery conditions met speed=%.2f home_distance=%.2f alt=%.2f",
                        telemetry.airspeed_mps,
                        telemetry.home_distance_m,
                        telemetry.alt_m,
                    )
                    return True
            else:
                stable_since = None
            if self._sleep_with_cancel(cancel_event, 0.2):
                logger.info("Recovery wait cancelled during sleep")
                return False
        logger.warning("Recovery wait timed out after %.1fs", thresholds.timeout_seconds)
        return False

    def _sleep_with_cancel(self, cancel_event: threading.Event, duration_seconds: float, step_seconds: float = 0.1) -> bool:
        deadline = time.time() + duration_seconds
        while time.time() < deadline:
            if cancel_event.is_set():
                return True
            time.sleep(min(step_seconds, max(0.0, deadline - time.time())))
        return cancel_event.is_set()
