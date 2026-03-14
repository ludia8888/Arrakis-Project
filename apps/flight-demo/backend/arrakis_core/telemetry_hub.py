from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from schemas import MissionPhase, RoutePreview, TelemetrySnapshot

from .safety_manager import geofence_contains, should_trigger_battery_rtl
from .video_service import VideoService


logger = logging.getLogger("arrakis.telemetry")


@dataclass(frozen=True)
class SafetyDecision:
    trigger_battery_rtl: bool
    trigger_geofence_abort: bool
    trigger_telemetry_lost: bool

class TelemetryHub:
    def __init__(self, initial_snapshot: TelemetrySnapshot, video_service: VideoService) -> None:
        self.video_service = video_service
        self._lock = threading.Lock()
        self._telemetry = initial_snapshot
        self._was_telemetry_fresh = False

    def reset(self, snapshot: TelemetrySnapshot) -> None:
        with self._lock:
            self._telemetry = snapshot
            self._was_telemetry_fresh = False
        logger.info("Telemetry hub reset")

    def telemetry_snapshot(self) -> TelemetrySnapshot:
        with self._lock:
            return self._telemetry

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
        )
        updated = snapshot.model_copy(update={"geofence_breached": geofence_breached})
        with self._lock:
            self._telemetry = updated

        self.video_service.set_degrade_from_rtf(updated.sim_rtf)
        if geofence_breached:
            logger.warning("Geofence breach detected at lat=%.6f lon=%.6f", updated.lat, updated.lon)
        battery_rtl = updated.telemetry_fresh and updated.mode_valid and should_trigger_battery_rtl(updated)
        if battery_rtl:
            logger.warning("Battery threshold crossed at %.1f%%", updated.battery_percent)

        # Detect telemetry freshness loss: was fresh, now stale
        telemetry_lost = self._was_telemetry_fresh and not snapshot.telemetry_fresh
        self._was_telemetry_fresh = snapshot.telemetry_fresh
        if telemetry_lost:
            logger.warning("Telemetry freshness lost during phase=%s", phase)

        return SafetyDecision(
            trigger_battery_rtl=battery_rtl,
            trigger_geofence_abort=geofence_breached,
            trigger_telemetry_lost=telemetry_lost,
        )
