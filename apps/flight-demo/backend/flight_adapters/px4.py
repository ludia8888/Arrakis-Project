from __future__ import annotations

from schemas import LatLon, TelemetrySnapshot

from .base import FlightControllerAdapter


class PX4Adapter(FlightControllerAdapter):
    """Future adapter stub kept to preserve the cross-stack boundary."""

    def __init__(self) -> None:
        raise NotImplementedError("PX4Adapter is intentionally not implemented in the ArduPilot-first v1 demo.")

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
    def stream_telemetry(self, callback): raise NotImplementedError
    def stream_video(self, callback): raise NotImplementedError
    def get_home(self) -> LatLon: raise NotImplementedError
