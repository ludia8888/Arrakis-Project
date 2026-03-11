from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

from schemas import AdapterBootstrapStatus, LatLon, TelemetrySnapshot


@dataclass
class VideoFrame:
    timestamp: float
    frame_bgr: Any
    fps: float
    latency_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class FlightControllerAdapterContract(Protocol):
    def mission_execution_style(self) -> str: ...
    def connect(self) -> None: ...
    def arm(self) -> None: ...
    def takeoff_multicopter(self, target_alt_m: float) -> None: ...
    def upload_roundtrip_mission(self, route_spec: dict[str, Any]) -> None: ...
    def start_mission(self) -> None: ...
    def transition_to_fixedwing(self) -> None: ...
    def prepare_multicopter_recovery(self, recovery_spec: dict[str, Any]) -> None: ...
    def transition_to_multicopter(self) -> None: ...
    def return_to_home(self) -> None: ...
    def land_vertical(self) -> None: ...
    def abort(self, reason: str) -> None: ...
    def reset(self) -> None: ...
    def get_snapshot(self) -> TelemetrySnapshot: ...
    def current_leg(self) -> str: ...
    def stream_telemetry(self, callback: Callable[[TelemetrySnapshot], None]) -> None: ...
    def stream_video(self, callback: Callable[[VideoFrame], None]) -> None: ...
    def get_home(self) -> LatLon: ...
    def bootstrap_status(self) -> AdapterBootstrapStatus: ...


REQUIRED_ADAPTER_METHODS = (
    "mission_execution_style",
    "connect",
    "arm",
    "takeoff_multicopter",
    "upload_roundtrip_mission",
    "start_mission",
    "transition_to_fixedwing",
    "prepare_multicopter_recovery",
    "transition_to_multicopter",
    "return_to_home",
    "land_vertical",
    "abort",
    "reset",
    "get_snapshot",
    "current_leg",
    "stream_telemetry",
    "stream_video",
    "get_home",
    "bootstrap_status",
)


def validate_adapter_contract(adapter: object) -> FlightControllerAdapterContract:
    missing = [name for name in REQUIRED_ADAPTER_METHODS if not callable(getattr(adapter, name, None))]
    if missing:
        raise TypeError(
            f"Adapter {type(adapter).__name__} is missing required callable methods: {', '.join(sorted(missing))}"
        )
    if not isinstance(adapter, FlightControllerAdapterContract):
        raise TypeError(f"Adapter {type(adapter).__name__} does not satisfy FlightControllerAdapterContract")
    return adapter


class FlightControllerAdapter(ABC):
    @abstractmethod
    def mission_execution_style(self) -> str: ...

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
    def current_leg(self) -> str: ...

    @abstractmethod
    def stream_telemetry(self, callback: Callable[[TelemetrySnapshot], None]) -> None: ...

    @abstractmethod
    def stream_video(self, callback: Callable[[VideoFrame], None]) -> None: ...

    @abstractmethod
    def get_home(self) -> LatLon: ...

    @abstractmethod
    def bootstrap_status(self) -> AdapterBootstrapStatus: ...
