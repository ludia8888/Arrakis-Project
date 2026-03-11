from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from schemas import (
    LatLon,
    RoutePreview,
    RouteProgress,
    StatePayload,
    TelemetrySnapshot,
)

from .safety_manager import geofence_contains, should_trigger_battery_rtl
from .video_service import VideoService


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

    def telemetry_snapshot(self) -> TelemetrySnapshot:
        with self._lock:
            return self._telemetry

    def on_telemetry(self, snapshot: TelemetrySnapshot, route_preview: RoutePreview | None) -> SafetyDecision:
        geofence_breached = not geofence_contains(route_preview.geofence if route_preview else None, snapshot)
        updated = snapshot.model_copy(update={"geofence_breached": geofence_breached})
        with self._lock:
            self._telemetry = updated

        self.video_service.set_degrade_from_rtf(updated.sim_rtf)

        return SafetyDecision(
            trigger_battery_rtl=should_trigger_battery_rtl(updated),
            trigger_geofence_abort=geofence_breached,
        )

    def state_payload(
        self,
        *,
        mission_phase,
        abort_reason: str | None,
        route_preview: RoutePreview | None,
        current_leg: str,
    ) -> StatePayload:
        with self._lock:
            telemetry = self._telemetry
        progress = RouteProgress(
            outbound_total=len(route_preview.outbound) if route_preview else 0,
            return_total=len(route_preview.return_path) if route_preview else 0,
            current_leg=current_leg,
            current_waypoint_index=telemetry.mission_index,
            next_waypoint=self._next_waypoint(route_preview, telemetry.mission_index),
        )
        return StatePayload(
            timestamp=time.time(),
            mission_phase=mission_phase,
            abort_reason=abort_reason,
            telemetry=telemetry,
            route_progress=progress,
            detector=self.video_service.detector_state(),
            simulator=self.video_service.simulator_state(telemetry.sim_rtf),
            geofence=route_preview.geofence if route_preview else None,
            route_home=route_preview.home if route_preview else None,
            outbound=route_preview.outbound if route_preview else [],
            return_path=route_preview.return_path if route_preview else [],
        )

    def _next_waypoint(self, route_preview: RoutePreview | None, mission_index: int) -> LatLon | None:
        if not route_preview:
            return None
        route = route_preview.outbound + route_preview.return_path
        if 0 <= mission_index < len(route):
            return route[mission_index]
        return route_preview.home
