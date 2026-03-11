from __future__ import annotations

import logging

from schemas import LatLon, TelemetrySnapshot

from .base import FlightControllerAdapter, VideoFrame


logger = logging.getLogger("arrakis.adapter.ardupilot")


class ArduPilotAdapter(FlightControllerAdapter):
    """Reserved for real SITL integration.

    v1 ships the adapter boundary and a working mock path first.

    Intended real integration policy:
    - Try MAVSDK first for connection, telemetry subscription, and mission-level control.
    - Verify ArduPilot VTOL transition behavior explicitly against DO_VTOL_TRANSITION and mission-item support.
    - If MAVSDK does not expose the needed VTOL operations reliably, keep the same adapter contract and
      use pymavlink internally for low-level command delivery.
    - Video ingestion remains adapter-owned and should expose camera frames only through stream_video().
    """

    def __init__(self) -> None:
        logger.info("ArduPilotAdapter scaffold instantiated")
        raise NotImplementedError("ArduPilotAdapter is scaffolded but not wired in this v1 build.")

    def connect(self) -> None: raise NotImplementedError
    def arm(self) -> None: raise NotImplementedError
    def takeoff_multicopter(self, target_alt_m: float) -> None: raise NotImplementedError
    def upload_roundtrip_mission(self, route_spec: dict[str, object]) -> None: raise NotImplementedError
    def start_mission(self) -> None: raise NotImplementedError
    def transition_to_fixedwing(self) -> None: raise NotImplementedError
    def prepare_multicopter_recovery(self, recovery_spec: dict[str, object]) -> None: raise NotImplementedError
    def transition_to_multicopter(self) -> None: raise NotImplementedError
    def return_to_home(self) -> None: raise NotImplementedError
    def land_vertical(self) -> None: raise NotImplementedError
    def abort(self, reason: str) -> None: raise NotImplementedError
    def reset(self) -> None: raise NotImplementedError
    def get_snapshot(self) -> TelemetrySnapshot: raise NotImplementedError
    def current_leg(self) -> str: raise NotImplementedError
    def stream_telemetry(self, callback): raise NotImplementedError
    def stream_video(self, callback): raise NotImplementedError
    def get_home(self) -> LatLon: raise NotImplementedError
