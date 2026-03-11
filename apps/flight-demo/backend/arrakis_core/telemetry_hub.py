from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from schemas import RoutePreview, TelemetrySnapshot

from .safety_manager import geofence_contains, should_trigger_battery_rtl
from .video_service import VideoService


logger = logging.getLogger("arrakis.telemetry")


@dataclass(frozen=True)
class SafetyDecision:
    trigger_battery_rtl: bool
    trigger_geofence_abort: bool

class TelemetryHub:
    def __init__(self, initial_snapshot: TelemetrySnapshot, video_service: VideoService) -> None:
        self.video_service = video_service
        self._lock = threading.Lock()
        self._telemetry = initial_snapshot

    def reset(self, snapshot: TelemetrySnapshot) -> None:
        with self._lock:
            self._telemetry = snapshot
        logger.info("Telemetry hub reset")

    def telemetry_snapshot(self) -> TelemetrySnapshot:
        with self._lock:
            return self._telemetry

    def on_telemetry(self, snapshot: TelemetrySnapshot, route_preview: RoutePreview | None) -> SafetyDecision:
        geofence_breached = not geofence_contains(route_preview.geofence if route_preview else None, snapshot)
        updated = snapshot.model_copy(update={"geofence_breached": geofence_breached})
        with self._lock:
            self._telemetry = updated

        self.video_service.set_degrade_from_rtf(updated.sim_rtf)
        if geofence_breached:
            logger.warning("Geofence breach detected at lat=%.6f lon=%.6f", updated.lat, updated.lon)
        if should_trigger_battery_rtl(updated):
            logger.warning("Battery threshold crossed at %.1f%%", updated.battery_percent)

        return SafetyDecision(
            trigger_battery_rtl=should_trigger_battery_rtl(updated),
            trigger_geofence_abort=geofence_breached,
        )
