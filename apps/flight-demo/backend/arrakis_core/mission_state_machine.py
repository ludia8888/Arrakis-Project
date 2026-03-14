from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from schemas import MissionPhase, RoutePreview


TERMINAL_PHASES = {"IDLE", "COMPLETE", "ABORT_GEOFENCE", "ABORT_MANUAL"}
INTERRUPT_PHASES = {"ABORT_GEOFENCE", "ABORT_MANUAL", "RTL_BATTERY"}


logger = logging.getLogger("arrakis.state_machine")


@dataclass(frozen=True)
class MissionStatus:
    phase: MissionPhase
    abort_reason: str | None
    route_preview: RoutePreview | None


class MissionStateMachine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._phase: MissionPhase = "IDLE"
        self._abort_reason: str | None = None
        self._route_preview: RoutePreview | None = None

    def snapshot(self) -> MissionStatus:
        with self._lock:
            return MissionStatus(
                phase=self._phase,
                abort_reason=self._abort_reason,
                route_preview=self._route_preview,
            )

    def set_route(self, preview: RoutePreview, mission_active: bool) -> RoutePreview:
        with self._lock:
            if mission_active and self._phase not in TERMINAL_PHASES:
                raise RuntimeError("Mission is active. Reset or abort before uploading a new route.")
            previous = self._phase
            self._route_preview = preview
            self._phase = "IDLE"
            self._abort_reason = None
            if previous != self._phase:
                logger.info(
                    "Phase transition %s -> %s reason=route loaded outbound=%d return=%d",
                    previous,
                    self._phase,
                    len(preview.outbound),
                    len(preview.return_path),
                )
            else:
                logger.info("Route loaded in phase=%s outbound=%d return=%d", self._phase, len(preview.outbound), len(preview.return_path))
            return preview

    def require_route(self) -> RoutePreview:
        with self._lock:
            if self._route_preview is None:
                raise ValueError("Route must be set before starting a mission.")
            return self._route_preview

    def start_mission(self, mission_active: bool) -> RoutePreview:
        with self._lock:
            if self._route_preview is None:
                raise ValueError("Route must be set before starting a mission.")
            if mission_active:
                raise RuntimeError("Mission is already running.")
            if self._phase not in TERMINAL_PHASES:
                raise RuntimeError("Mission is not in a startable state.")
            self._abort_reason = None
            self._phase = "STARTING"
            logger.info("Mission start accepted, phase set to STARTING")
            return self._route_preview

    def mark_phase(self, phase: MissionPhase, reason: str | None = None) -> None:
        with self._lock:
            previous = self._phase
            self._phase = phase
            if previous != phase:
                logger.info("Phase transition %s -> %s reason=%s", previous, phase, reason or "unspecified")

    def abort(self, phase: MissionPhase, reason: str) -> None:
        with self._lock:
            logger.warning("Abort transition %s -> %s reason=%s", self._phase, phase, reason)
            self._phase = phase
            self._abort_reason = reason

    def clear_abort_reason(self) -> None:
        with self._lock:
            self._abort_reason = None

    def complete(self) -> None:
        with self._lock:
            logger.info("Phase transition %s -> COMPLETE reason=landing complete", self._phase)
            self._phase = "COMPLETE"

    def reset(self) -> None:
        with self._lock:
            if self._phase != "IDLE":
                logger.info("Phase transition %s -> IDLE reason=state machine reset", self._phase)
            else:
                logger.info("State machine reset while already in IDLE")
            self._phase = "IDLE"
            self._abort_reason = None
            self._route_preview = None

    @property
    def route_preview(self) -> RoutePreview | None:
        with self._lock:
            return self._route_preview

    @property
    def phase(self) -> MissionPhase:
        with self._lock:
            return self._phase

    @property
    def abort_reason(self) -> str | None:
        with self._lock:
            return self._abort_reason
