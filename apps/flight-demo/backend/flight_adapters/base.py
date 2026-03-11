from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from schemas import LatLon, TelemetrySnapshot


@dataclass
class VideoFrame:
    timestamp: float
    frame_bgr: Any
    fps: float
    latency_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


class FlightControllerAdapter(ABC):
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def arm(self) -> None: ...

    @abstractmethod
    def takeoff_multicopter(self, target_alt_m: float) -> None: ...

    @abstractmethod
    def upload_roundtrip_mission(self, route_spec: dict[str, Any]) -> None: ...

    @abstractmethod
    def start_mission(self) -> None: ...

    @abstractmethod
    def transition_to_fixedwing(self) -> None: ...

    @abstractmethod
    def prepare_multicopter_recovery(self, recovery_spec: dict[str, Any]) -> None: ...

    @abstractmethod
    def transition_to_multicopter(self) -> None: ...

    @abstractmethod
    def return_to_home(self) -> None: ...

    @abstractmethod
    def land_vertical(self) -> None: ...

    @abstractmethod
    def abort(self, reason: str) -> None: ...

    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    def get_snapshot(self) -> TelemetrySnapshot: ...

    @abstractmethod
    def stream_telemetry(self, callback: Callable[[TelemetrySnapshot], None]) -> None: ...

    @abstractmethod
    def stream_video(self, callback: Callable[[VideoFrame], None]) -> None: ...

    @abstractmethod
    def get_home(self) -> LatLon: ...
