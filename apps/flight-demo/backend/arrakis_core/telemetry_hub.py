from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from airframe_profile import AirframeProfile
from config import ARRAKIS_LINK_PROFILE
from schemas import MissionPhase, RoutePreview, StressEnvelope, TelemetrySnapshot

from .safety_manager import geofence_contains, should_trigger_battery_rtl
from .video_service import VideoService


logger = logging.getLogger("arrakis.telemetry")
_monotonic = time.monotonic


@dataclass(frozen=True)
class SafetyDecision:
    trigger_battery_rtl: bool
    trigger_geofence_abort: bool
    trigger_telemetry_lost: bool
    trigger_position_loss_rtl: bool
    trigger_navigation_degraded_rtl: bool

class TelemetryHub:
    def __init__(self, initial_snapshot: TelemetrySnapshot, video_service: VideoService, profile: AirframeProfile) -> None:
        self.video_service = video_service
        self.profile = profile
        self._link_profile = ARRAKIS_LINK_PROFILE
        self._lock = threading.Lock()
        self._telemetry = initial_snapshot
        self._telemetry_lost_samples = 0
        self._telemetry_lost_active = False
        self._position_invalid_since_mono: float | None = None
        self._position_loss_triggered = False
        self._navigation_degraded_since_mono: float | None = None
        self._navigation_degraded_triggered = False
        self._progress_phase: MissionPhase | None = None
        self._progress_reference_mission_index: int | None = None
        self._progress_reference_home_distance_m: float | None = None
        self._previous_snapshot: TelemetrySnapshot | None = initial_snapshot
        self._stress = self._build_stress_envelope(initial_snapshot, "IDLE")

    def reset(self, snapshot: TelemetrySnapshot) -> None:
        with self._lock:
            self._telemetry = snapshot
            self._stress = self._build_stress_envelope(snapshot, "IDLE")
            self._telemetry_lost_samples = 0
            self._telemetry_lost_active = False
            self._position_invalid_since_mono = None
            self._position_loss_triggered = False
            self._navigation_degraded_since_mono = None
            self._navigation_degraded_triggered = False
            self._progress_phase = None
            self._progress_reference_mission_index = None
            self._progress_reference_home_distance_m = None
            self._previous_snapshot = snapshot
        logger.info("Telemetry hub reset")

    def telemetry_snapshot(self) -> TelemetrySnapshot:
        with self._lock:
            return self._telemetry

    def stress_envelope(self) -> StressEnvelope:
        with self._lock:
            return self._stress

    def on_telemetry(
        self,
        snapshot: TelemetrySnapshot,
        route_preview: RoutePreview | None,
        phase: MissionPhase,
    ) -> SafetyDecision:
        geofence_eligible = bool(
            route_preview
            and snapshot.telemetry_fresh
            and snapshot.mode_valid
            and snapshot.position_valid
            and snapshot.home_valid
        )
        route_home = (route_preview.home.lat, route_preview.home.lon) if route_preview else None
        geofence_breached = geofence_eligible and not geofence_contains(
            route_preview.geofence if route_preview else None,
            snapshot,
            phase,
            route_home,
            profile=self.profile,
        )
        updated = snapshot.model_copy(update={"geofence_breached": geofence_breached})
        with self._lock:
            self._telemetry = updated

        self.video_service.set_degrade_from_rtf(updated.sim_rtf)
        if geofence_breached:
            logger.warning("Geofence breach detected at lat=%.6f lon=%.6f", updated.lat, updated.lon)
        battery_rtl = updated.telemetry_fresh and updated.mode_valid and should_trigger_battery_rtl(updated, profile=self.profile)
        if battery_rtl:
            logger.warning("Battery threshold crossed at %.1f%%", updated.battery_percent)

        telemetry_lost = False
        if updated.telemetry_state == "lost":
            self._telemetry_lost_samples += 1
            if (
                self._telemetry_lost_samples >= self._link_profile.telemetry_stale_debounce
                and not self._telemetry_lost_active
            ):
                self._telemetry_lost_active = True
                telemetry_lost = True
        else:
            self._telemetry_lost_samples = 0
            self._telemetry_lost_active = False
        if telemetry_lost:
            logger.warning(
                "Telemetry lost during phase=%s age=%.2fs profile=%s",
                phase,
                updated.telemetry_age_s or -1.0,
                self._link_profile.name,
            )

        position_loss_rtl = False
        if (
            updated.telemetry_fresh
            and updated.mode_valid
            and updated.armed
            and not updated.position_valid
        ):
            now_mono = _monotonic()
            if self._position_invalid_since_mono is None:
                self._position_invalid_since_mono = now_mono
            elif (
                not self._position_loss_triggered
                and now_mono - self._position_invalid_since_mono >= self._link_profile.position_loss_rtl_timeout_s
            ):
                self._position_loss_triggered = True
                position_loss_rtl = True
                logger.warning(
                    "Position invalid for %.1fs during phase=%s, requesting RTL",
                    now_mono - self._position_invalid_since_mono,
                    phase,
                )
        else:
            self._position_invalid_since_mono = None
            self._position_loss_triggered = False

        navigation_reasons = self._navigation_degradation_reasons(updated, phase)
        stress = self._build_stress_envelope(updated, phase, navigation_reasons=navigation_reasons)
        with self._lock:
            self._stress = stress
        navigation_degraded_rtl = False
        navigation_timeout_s = self._navigation_timeout_seconds(navigation_reasons)
        if (
            updated.telemetry_fresh
            and updated.mode_valid
            and updated.armed
            and not position_loss_rtl
            and navigation_reasons
        ):
            now_mono = _monotonic()
            if self._navigation_degraded_since_mono is None:
                self._navigation_degraded_since_mono = now_mono
            elif (
                not self._navigation_degraded_triggered
                and now_mono - self._navigation_degraded_since_mono
                >= navigation_timeout_s
            ):
                self._navigation_degraded_triggered = True
                navigation_degraded_rtl = True
                logger.warning(
                    "Navigation degraded for %.1fs during phase=%s reasons=%s, requesting RTL",
                    now_mono - self._navigation_degraded_since_mono,
                    phase,
                    ",".join(navigation_reasons),
                )
        else:
            self._navigation_degraded_since_mono = None
            self._navigation_degraded_triggered = False

        self._previous_snapshot = updated

        return SafetyDecision(
            trigger_battery_rtl=battery_rtl,
            trigger_geofence_abort=geofence_breached,
            trigger_telemetry_lost=telemetry_lost,
            trigger_position_loss_rtl=position_loss_rtl,
            trigger_navigation_degraded_rtl=navigation_degraded_rtl,
        )

    def _build_stress_envelope(
        self,
        snapshot: TelemetrySnapshot,
        phase: MissionPhase,
        *,
        navigation_reasons: list[str] | None = None,
    ) -> StressEnvelope:
        wind_load_score = self._wind_load_score(snapshot)
        gps_degradation_score = self._gps_degradation_score(snapshot)
        sensor_noise_score = self._sensor_noise_score(snapshot, phase)
        progress_stall_score = self._progress_stall_score(
            snapshot,
            phase,
            stalled=(navigation_reasons is not None and "progress_stalled" in navigation_reasons),
        )
        overall_score = max(
            wind_load_score * 0.7,
            gps_degradation_score,
            sensor_noise_score * 0.9,
            progress_stall_score,
            min(
                1.0,
                (wind_load_score * 0.35)
                + (gps_degradation_score * 0.35)
                + (sensor_noise_score * 0.15)
                + (progress_stall_score * 0.35),
            ),
        )
        reasons: list[str] = []
        if wind_load_score >= 0.45:
            reasons.append("wind_load")
        if gps_degradation_score >= 0.35:
            reasons.append("gps_degradation")
        if sensor_noise_score >= 0.35:
            reasons.append("sensor_noise")
        if progress_stall_score >= 0.35:
            reasons.append("progress_stall")
        return StressEnvelope(
            level=self._stress_level(overall_score),
            overall_score=round(overall_score, 3),
            wind_load_score=round(wind_load_score, 3),
            gps_degradation_score=round(gps_degradation_score, 3),
            sensor_noise_score=round(sensor_noise_score, 3),
            progress_stall_score=round(progress_stall_score, 3),
            reasons=reasons,
        )

    def _stress_level(self, score: float) -> str:
        if score >= 0.85:
            return "critical"
        if score >= 0.65:
            return "severe"
        if score >= 0.35:
            return "elevated"
        return "nominal"

    def _navigation_degradation_reasons(
        self,
        snapshot: TelemetrySnapshot,
        phase: MissionPhase,
    ) -> list[str]:
        reasons: list[str] = []
        if self._gps_quality_degraded(snapshot):
            reasons.append("gps_quality")
        if self._progress_stalled(snapshot, phase):
            reasons.append("progress_stalled")
        if self._sensor_inconsistent(snapshot, phase):
            reasons.append("sensor_inconsistent")
        return reasons

    def _navigation_timeout_seconds(self, reasons: list[str]) -> float:
        safety = self.profile.safety
        timeouts = []
        if "gps_quality" in reasons:
            timeouts.append(self._link_profile.gps_degraded_rtl_timeout_s)
        if "progress_stalled" in reasons:
            timeouts.append(safety.progress_stall_timeout_seconds)
        if "sensor_inconsistent" in reasons:
            timeouts.append(safety.sensor_inconsistency_timeout_seconds)
        return min(timeouts) if timeouts else self._link_profile.gps_degraded_rtl_timeout_s

    def _gps_quality_degraded(self, snapshot: TelemetrySnapshot) -> bool:
        if not snapshot.gps_sensor_valid:
            return True
        fix_type = snapshot.gps_fix_type
        satellites = snapshot.gps_satellites
        if fix_type is not None and fix_type < self.profile.safety.min_gps_fix_type:
            return True
        if satellites is not None and satellites < self.profile.safety.min_gps_satellites:
            return True
        return False

    def _gps_degradation_score(self, snapshot: TelemetrySnapshot) -> float:
        if not snapshot.telemetry_fresh or not snapshot.mode_valid:
            return 0.0
        if not snapshot.position_valid:
            return 1.0
        if not snapshot.gps_sensor_valid:
            return 0.65
        fix_type = snapshot.gps_fix_type or self.profile.safety.min_gps_fix_type
        satellites = snapshot.gps_satellites or self.profile.safety.min_gps_satellites
        fix_gap = max(self.profile.safety.min_gps_fix_type - fix_type, 0)
        sat_gap = max(self.profile.safety.min_gps_satellites - satellites, 0)
        fix_score = min(fix_gap / 2.0, 1.0)
        sat_score = min(sat_gap / max(self.profile.safety.min_gps_satellites, 1), 1.0)
        return max(fix_score, sat_score)

    def _wind_load_score(self, snapshot: TelemetrySnapshot) -> float:
        if not snapshot.telemetry_fresh or not snapshot.mode_valid or not snapshot.armed:
            return 0.0
        if snapshot.airspeed_mps <= 0.1:
            return 0.0
        headwind_gap = max(snapshot.airspeed_mps - snapshot.groundspeed_mps, 0.0)
        return min(
            headwind_gap / max(self.profile.safety.min_progress_airspeed_mps, 1.0),
            1.0,
        )

    def _progress_stalled(
        self,
        snapshot: TelemetrySnapshot,
        phase: MissionPhase,
    ) -> bool:
        eligible = (
            snapshot.telemetry_fresh
            and snapshot.mode_valid
            and snapshot.position_valid
            and snapshot.home_valid
            and snapshot.armed
            and phase in {"OUTBOUND", "RETURN"}
        )
        if not eligible:
            self._progress_phase = None
            self._progress_reference_mission_index = None
            self._progress_reference_home_distance_m = None
            return False

        if self._progress_phase != phase:
            self._progress_phase = phase
            self._progress_reference_mission_index = snapshot.mission_index
            self._progress_reference_home_distance_m = snapshot.home_distance_m
            return False

        reference_index = self._progress_reference_mission_index
        reference_home_distance = self._progress_reference_home_distance_m
        progressed = False
        if reference_index is None or reference_home_distance is None:
            progressed = True
        elif snapshot.mission_index != reference_index:
            progressed = True
        elif (
            phase == "OUTBOUND"
            and snapshot.home_distance_m >= reference_home_distance + self.profile.safety.progress_min_delta_m
        ):
            progressed = True
        elif (
            phase == "RETURN"
            and snapshot.home_distance_m <= reference_home_distance - self.profile.safety.progress_min_delta_m
        ):
            progressed = True

        if progressed:
            self._progress_reference_mission_index = snapshot.mission_index
            self._progress_reference_home_distance_m = snapshot.home_distance_m
            return False

        return (
            snapshot.airspeed_mps >= self.profile.safety.min_progress_airspeed_mps
            and snapshot.groundspeed_mps <= self.profile.safety.min_progress_groundspeed_mps
        )

    def _progress_stall_score(
        self,
        snapshot: TelemetrySnapshot,
        phase: MissionPhase,
        *,
        stalled: bool | None = None,
    ) -> float:
        if stalled is None:
            stalled = self._progress_stalled(snapshot, phase)
        if not stalled:
            return 0.0
        groundspeed_ratio = 1.0 - min(
            snapshot.groundspeed_mps / max(self.profile.safety.min_progress_groundspeed_mps, 0.1),
            1.0,
        )
        airspeed_ratio = min(
            snapshot.airspeed_mps / max(self.profile.safety.min_progress_airspeed_mps, 1.0),
            1.0,
        )
        return min(max(groundspeed_ratio, airspeed_ratio * 0.7), 1.0)

    def _sensor_inconsistent(
        self,
        snapshot: TelemetrySnapshot,
        phase: MissionPhase,
    ) -> bool:
        previous = self._previous_snapshot
        eligible = (
            snapshot.telemetry_fresh
            and snapshot.mode_valid
            and snapshot.position_valid
            and snapshot.armed
            and phase in {"OUTBOUND", "RETURN"}
        )
        if not eligible or previous is None:
            return False
        if not previous.telemetry_fresh or not previous.position_valid:
            return False
        dt = snapshot.timestamp - previous.timestamp
        if dt <= 0.0 or dt > 2.0:
            return False
        altitude_jump = abs(snapshot.alt_m - previous.alt_m)
        airspeed_jump = abs(snapshot.airspeed_mps - previous.airspeed_mps)
        return (
            altitude_jump >= self.profile.safety.sensor_inconsistency_altitude_jump_m
            or airspeed_jump >= self.profile.safety.sensor_inconsistency_airspeed_jump_mps
        )

    def _sensor_noise_score(
        self,
        snapshot: TelemetrySnapshot,
        phase: MissionPhase,
    ) -> float:
        previous = self._previous_snapshot
        if previous is None or not previous.telemetry_fresh or not previous.position_valid:
            return 0.0
        if not snapshot.telemetry_fresh or not snapshot.position_valid:
            return 0.0
        if phase not in {"OUTBOUND", "RETURN"}:
            return 0.0
        dt = snapshot.timestamp - previous.timestamp
        if dt <= 0.0 or dt > 2.0:
            return 0.0
        altitude_jump = abs(snapshot.alt_m - previous.alt_m)
        airspeed_jump = abs(snapshot.airspeed_mps - previous.airspeed_mps)
        altitude_ratio = altitude_jump / max(self.profile.safety.sensor_inconsistency_altitude_jump_m, 0.1)
        airspeed_ratio = airspeed_jump / max(self.profile.safety.sensor_inconsistency_airspeed_jump_mps, 0.1)
        return min(max(altitude_ratio, airspeed_ratio), 1.0)
