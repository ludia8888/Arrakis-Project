from __future__ import annotations

import logging
import time

from schemas import LatLon, RoutePreview, RouteProgress, StatePayload, StressEnvelope, TelemetrySnapshot, TransitionDiagnostics

from .video_service import VideoService


logger = logging.getLogger("arrakis.state_assembler")


class StatePayloadAssembler:
    def __init__(self, video_service: VideoService) -> None:
        self.video_service = video_service

    def build(
        self,
        *,
        telemetry: TelemetrySnapshot,
        mission_phase,
        abort_reason: str | None,
        route_preview: RoutePreview | None,
        current_leg: str,
        transition: TransitionDiagnostics,
        stress: StressEnvelope,
    ) -> StatePayload:
        progress = RouteProgress(
            outbound_total=len(route_preview.outbound) if route_preview else 0,
            return_total=len(route_preview.return_path) if route_preview else 0,
            current_leg=current_leg,
            current_waypoint_index=telemetry.mission_index,
            next_waypoint=self._next_waypoint(route_preview, telemetry.mission_index),
        )
        payload = StatePayload(
            timestamp=time.time(),
            mission_phase=mission_phase,
            abort_reason=abort_reason,
            telemetry=telemetry,
            route_progress=progress,
            detector=self.video_service.detector_state(),
            simulator=self.video_service.simulator_state(telemetry.sim_rtf),
            transition=transition,
            stress=stress,
            geofence=route_preview.geofence if route_preview else None,
            route_home=route_preview.home if route_preview else None,
            outbound=route_preview.outbound if route_preview else [],
            return_path=route_preview.return_path if route_preview else [],
        )
        logger.debug(
            "Built state payload phase=%s current_leg=%s mission_index=%d",
            mission_phase,
            current_leg,
            telemetry.mission_index,
        )
        return payload

    def _next_waypoint(self, route_preview: RoutePreview | None, mission_index: int) -> LatLon | None:
        if not route_preview:
            return None
        route = route_preview.outbound + route_preview.return_path
        if 0 <= mission_index < len(route):
            return route[mission_index]
        return route_preview.home
