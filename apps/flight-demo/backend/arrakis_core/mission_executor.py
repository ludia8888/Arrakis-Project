from __future__ import annotations

import logging
import threading
import time

from airframe_profile import AirframeProfile
from flight_adapters.base import FlightControllerAdapter

from .mission_state_machine import INTERRUPT_PHASES, MissionStateMachine
from .telemetry_hub import TelemetryHub


logger = logging.getLogger("arrakis.executor")

ARDUPILOT_AUTOLAND_MODES = {"QRTL", "QLAND", "QLOITER"}


class MissionExecutor:
    def __init__(
        self,
        *,
        adapter: FlightControllerAdapter,
        state_machine: MissionStateMachine,
        telemetry_hub: TelemetryHub,
        profile: AirframeProfile,
    ) -> None:
        self.adapter = adapter
        self.state_machine = state_machine
        self.telemetry_hub = telemetry_hub
        self.profile = profile

    def run_roundtrip_mission(self, cancel_event: threading.Event) -> None:
        route_preview = self.state_machine.require_route()
        execution_style = self.adapter.mission_execution_style()
        if cancel_event.is_set():
            logger.info("Mission cancelled before start")
            return
        if not self._ensure_control_plane_available("mission start"):
            return
        self.state_machine.mark_phase("ARMING", reason="mission executor started arming sequence")
        self.adapter.arm()
        # Fix 12: battery check after arm
        if not self._check_battery_threshold():
            return
        if self._sleep_with_cancel(cancel_event, 1.0):
            logger.info("Mission cancelled during ARMING, disarming vehicle")
            with suppress(Exception):
                self.adapter.abort("cancelled during arm")
            return

        if execution_style == "mission_oriented":
            self._run_mission_oriented_roundtrip(route_preview, cancel_event)
            return

        self.state_machine.mark_phase("TAKEOFF_MC", reason="arm complete, takeoff requested")
        self.adapter.takeoff_multicopter(self.profile.altitudes.takeoff_m)
        # Fix 12: battery check after takeoff
        if not self._check_battery_threshold():
            return
        if self._sleep_with_cancel(cancel_event, 1.0):
            logger.info("Mission cancelled during TAKEOFF_MC")
            return

        self.adapter.upload_roundtrip_mission(
            {
                "outbound": [point.model_dump() for point in route_preview.outbound],
                "return_path": [point.model_dump() for point in route_preview.return_path],
                "geofence": [point.model_dump() for point in route_preview.geofence.coordinates],
            },
        )
        self.adapter.start_mission()
        if self.profile.is_vtol:
            self.state_machine.mark_phase("TRANSITION_FW", reason="mission uploaded, switching to fixed-wing in AUTO")
            self.adapter.transition_to_fixedwing()
            # Fix 12: battery check after FW transition
            if not self._check_battery_threshold():
                return
        self.state_machine.mark_phase("OUTBOUND", reason="mission uploaded and started")
        logger.info("Entered OUTBOUND")

        while True:
            if cancel_event.is_set() or self.state_machine.phase in INTERRUPT_PHASES:
                logger.info("Mission interrupted during outbound/return loop phase=%s", self.state_machine.phase)
                return
            if not self._ensure_control_plane_available("route progression"):
                return
            current_leg = self.adapter.current_leg()
            telemetry = self.telemetry_hub.telemetry_snapshot()
            # Fix 11: GPS health gate — suspend position-based decisions when GPS invalid
            if not telemetry.position_valid and telemetry.armed:
                logger.warning("GPS invalid during %s, suspending phase transitions", self.state_machine.phase)
                if self._sleep_with_cancel(cancel_event, 1.0):
                    return
                continue
            if current_leg == "return" and self.state_machine.phase != "RETURN":
                self.state_machine.mark_phase("RETURN", reason="adapter reported return leg")
                logger.info("Leg transitioned to RETURN")
            if current_leg == "idle" and telemetry.home_distance_m <= self.profile.geometry.home_arrival_radius_m:
                break
            if self._sleep_with_cancel(cancel_event, 0.2):
                logger.info("Mission cancelled during route progression")
                return

        if self.profile.is_vtol:
            self.state_machine.mark_phase("PRE_MC_RECOVERY", reason="route complete, preparing multicopter recovery")
            logger.info("Entered PRE_MC_RECOVERY")
            self.adapter.prepare_multicopter_recovery(
                {
                    "recovery_center": route_preview.home.model_dump(),
                    "target_alt_m": self.profile.altitudes.recovery_m,
                    "loiter_radius_m": self.profile.geometry.loiter_radius_m,
                },
            )
            if not self._wait_for_recovery(self.profile.recovery.primary, cancel_event):
                if self.state_machine.abort_reason:
                    logger.warning("Primary recovery ended due to abort reason=%s", self.state_machine.abort_reason)
                    return
                if cancel_event.is_set():
                    logger.info("Mission cancelled during primary recovery")
                    return
                logger.warning("Primary recovery timed out, attempting fallback recovery")
                self.adapter.return_to_home()
                if not self._wait_for_recovery(self.profile.recovery.fallback, cancel_event):
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

        self.state_machine.mark_phase("LANDING", reason="vertical landing requested")
        self.adapter.land_vertical()
        self._wait_for_landing(cancel_event)

    def _run_mission_oriented_roundtrip(self, route_preview, cancel_event: threading.Event) -> None:
        self.adapter.upload_roundtrip_mission(
            {
                "home": route_preview.home.model_dump(),
                "outbound": [point.model_dump() for point in route_preview.outbound],
                "return_path": [point.model_dump() for point in route_preview.return_path],
                "geofence": [point.model_dump() for point in route_preview.geofence.coordinates],
                "takeoff_alt_m": self.profile.altitudes.takeoff_m,
                "cruise_alt_m": route_preview.cruise_alt_m,
            },
        )
        self.adapter.start_mission()
        # Fix 12: battery check after mission start
        if not self._check_battery_threshold():
            return
        takeoff_reason = "ArduPilot mission started with NAV_VTOL_TAKEOFF" if self.profile.is_vtol else "ArduPilot mission started with NAV_TAKEOFF"
        self.state_machine.mark_phase("TAKEOFF_MC", reason=takeoff_reason)
        if not self._wait_for_condition(
            cancel_event,
            timeout_seconds=self.profile.timing.takeoff_timeout_seconds,
            description="mission takeoff climb",
            predicate=lambda telemetry: telemetry.alt_m >= self.profile.altitudes.takeoff_m * 0.7,
        ):
            return
        if self.profile.is_vtol:
            self.state_machine.mark_phase("TRANSITION_FW", reason="ArduPilot mission progressing through VTOL transition")
        if not self._wait_for_condition(
            cancel_event,
            timeout_seconds=self.profile.timing.transition_timeout_seconds,
            description="mission outbound leg",
            predicate=lambda telemetry: self.adapter.current_leg() == "outbound",
        ):
            return
        self.state_machine.mark_phase("OUTBOUND", reason="adapter reported outbound leg")
        logger.info("Entered OUTBOUND via mission-oriented ArduPilot path")

        while True:
            if cancel_event.is_set() or self.state_machine.phase in INTERRUPT_PHASES:
                logger.info("Mission interrupted during outbound/return loop phase=%s", self.state_machine.phase)
                return
            if not self._ensure_control_plane_available("mission-oriented route progression"):
                return
            current_leg = self.adapter.current_leg()
            telemetry = self.telemetry_hub.telemetry_snapshot()
            # Fix 11: GPS health gate — suspend position-based decisions when GPS invalid
            if not telemetry.position_valid and telemetry.armed:
                logger.warning("GPS invalid during %s (mission-oriented), suspending phase transitions", self.state_machine.phase)
                if self._sleep_with_cancel(cancel_event, 1.0):
                    return
                continue
            if current_leg == "return" and self.state_machine.phase != "RETURN":
                self.state_machine.mark_phase("RETURN", reason="adapter reported return leg")
                logger.info("Leg transitioned to RETURN")
            if current_leg == "landing" or self._ardupilot_autoland_active(telemetry):
                logger.info(
                    "Mission-oriented ArduPilot path entering mission-driven landing leg=%s mode=%s home_distance=%.1f alt=%.1f",
                    current_leg,
                    telemetry.flight_mode,
                    telemetry.home_distance_m,
                    telemetry.alt_m,
                )
                if self.profile.is_vtol:
                    self.state_machine.mark_phase(
                        "PRE_MC_RECOVERY",
                        reason=f"ArduPilot mission entered landing phase ({current_leg}/{telemetry.flight_mode})",
                    )
                    self.state_machine.mark_phase(
                        "TRANSITION_MC",
                        reason="ArduPilot mission is handling multicopter recovery/transition",
                    )
                self.state_machine.mark_phase(
                    "LANDING",
                    reason=f"monitoring mission-driven ArduPilot landing in {telemetry.flight_mode}",
                )
                self._wait_for_landing(cancel_event)
                return
            if current_leg == "idle" and not telemetry.armed and telemetry.home_distance_m <= self.profile.geometry.home_arrival_radius_m:
                if self.state_machine.phase not in INTERRUPT_PHASES:
                    self.state_machine.complete()
                    logger.info("Mission reached COMPLETE after mission-driven landing disarm")
                else:
                    logger.info("Mission-driven disarm but phase=%s is interrupt, skipping complete()", self.state_machine.phase)
                return
            if self._sleep_with_cancel(cancel_event, 0.2):
                logger.info("Mission cancelled during route progression")
                return

    def _wait_for_recovery(self, thresholds, cancel_event: threading.Event) -> bool:
        deadline = time.time() + thresholds.timeout_seconds
        stable_since: float | None = None
        while time.time() < deadline:
            if cancel_event.is_set():
                logger.info("Recovery wait cancelled")
                return False
            if not self._ensure_control_plane_available("recovery wait"):
                return False
            telemetry = self.telemetry_hub.telemetry_snapshot()
            if telemetry.geofence_breached:
                self.state_machine.abort("ABORT_GEOFENCE", "route-derived geofence breached")
                logger.warning("Recovery failed due to geofence breach")
                return False
            if telemetry.battery_percent <= self.profile.safety.battery_rtl_threshold_percent:
                self.state_machine.abort("RTL_BATTERY", "battery threshold reached")
                logger.warning("Recovery failed due to battery threshold at %.1f%%", telemetry.battery_percent)
                return False
            conditions_met = (
                telemetry.airspeed_mps <= thresholds.speed_threshold_mps
                and telemetry.home_distance_m <= thresholds.home_distance_threshold_m
                and abs(telemetry.alt_m - self.profile.altitudes.recovery_m) <= thresholds.altitude_deviation_m
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

    def _wait_for_landing(self, cancel_event: threading.Event) -> bool:
        deadline = time.time() + self.profile.timing.landing_timeout_seconds
        while True:
            if cancel_event.is_set():
                logger.info("Mission cancelled during LANDING")
                return False
            if not self._ensure_control_plane_available("landing wait"):
                return False
            telemetry = self.telemetry_hub.telemetry_snapshot()
            if not telemetry.armed:
                break
            if telemetry.telemetry_fresh and telemetry.position_valid and telemetry.alt_m <= 0.5:
                break
            if time.time() >= deadline:
                reason = f"timed out waiting for landing after {self.profile.timing.landing_timeout_seconds:.0f}s"
                logger.error(
                    "Landing wait timed out mode=%s armed=%s alt=%.2f home_distance=%.1f",
                    telemetry.flight_mode,
                    telemetry.armed,
                    telemetry.alt_m,
                    telemetry.home_distance_m,
                )
                self.state_machine.abort("ABORT_MANUAL", reason)
                try:
                    self.adapter.abort(reason)
                except Exception:
                    logger.exception("Adapter abort failed after landing timeout")
                # Fix 13: monitor armed state after abort for 5 seconds
                disarm_deadline = time.time() + 5.0
                while time.time() < disarm_deadline:
                    post_abort_telem = self.telemetry_hub.telemetry_snapshot()
                    if not post_abort_telem.armed:
                        logger.info("Vehicle disarmed after landing timeout abort")
                        break
                    time.sleep(0.5)
                else:
                    post_abort_telem = self.telemetry_hub.telemetry_snapshot()
                    if post_abort_telem.armed:
                        logger.critical(
                            "MANUAL INTERVENTION REQUIRED: vehicle still armed after landing timeout abort "
                            "mode=%s alt=%.2f",
                            post_abort_telem.flight_mode,
                            post_abort_telem.alt_m,
                        )
                return False
            if self._sleep_with_cancel(cancel_event, 0.2):
                logger.info("Mission cancelled while waiting for landing")
                return False
        if self.state_machine.phase not in INTERRUPT_PHASES:
            self.state_machine.complete()
            logger.info("Mission reached COMPLETE")
        else:
            logger.info("Landing finished but phase=%s is an interrupt phase, skipping complete()", self.state_machine.phase)
        return True

    def _ardupilot_autoland_active(self, telemetry) -> bool:
        return telemetry.flight_mode.upper() in ARDUPILOT_AUTOLAND_MODES

    # Fix 12: battery threshold check between critical flight commands
    def _check_battery_threshold(self) -> bool:
        """Check battery level and trigger RTL if below threshold.

        Returns True if battery is OK, False if RTL was triggered.
        """
        telemetry = self.telemetry_hub.telemetry_snapshot()
        if telemetry.battery_percent <= self.profile.safety.battery_rtl_threshold_percent:
            logger.warning(
                "Battery below RTL threshold (%.1f%% <= %.1f%%) during %s, triggering RTL",
                telemetry.battery_percent,
                self.profile.safety.battery_rtl_threshold_percent,
                self.state_machine.phase,
            )
            self.state_machine.abort("RTL_BATTERY", "battery threshold reached during transition")
            self.adapter.return_to_home()
            return False
        return True

    def _ensure_control_plane_available(self, context: str) -> bool:
        bootstrap = self.adapter.bootstrap_status()
        if not bootstrap.control_plane_fault:
            return True
        logger.error(
            "Control plane fault detected during %s kind=%s reason=%s",
            context,
            bootstrap.fault_kind,
            bootstrap.fault_reason,
        )
        self.state_machine.abort("RTL_LINK_LOSS", bootstrap.fault_reason or "control plane fault during flight")
        self.adapter.return_to_home()
        return False

    def _sleep_with_cancel(self, cancel_event: threading.Event, duration_seconds: float, step_seconds: float = 0.1) -> bool:
        deadline = time.time() + duration_seconds
        while time.time() < deadline:
            if cancel_event.is_set():
                return True
            time.sleep(min(step_seconds, max(0.0, deadline - time.time())))
        return cancel_event.is_set()

    def _wait_for_condition(
        self,
        cancel_event: threading.Event,
        *,
        timeout_seconds: float,
        description: str,
        predicate,
    ) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if cancel_event.is_set():
                logger.info("Condition wait cancelled description=%s", description)
                return False
            telemetry = self.telemetry_hub.telemetry_snapshot()
            if telemetry.geofence_breached:
                self.state_machine.abort("ABORT_GEOFENCE", "route-derived geofence breached")
                logger.warning("Condition wait failed due to geofence breach description=%s", description)
                return False
            if telemetry.battery_percent <= self.profile.safety.battery_rtl_threshold_percent:
                self.state_machine.abort("RTL_BATTERY", "battery threshold reached")
                logger.warning("Condition wait failed due to battery threshold description=%s", description)
                return False
            if predicate(telemetry):
                logger.info("Condition satisfied description=%s", description)
                return True
            if self._sleep_with_cancel(cancel_event, 0.2):
                logger.info("Condition wait cancelled during sleep description=%s", description)
                return False
        self.state_machine.abort("ABORT_MANUAL", f"timed out waiting for {description}")
        logger.error("Condition wait timed out description=%s timeout=%.1fs", description, timeout_seconds)
        return False
