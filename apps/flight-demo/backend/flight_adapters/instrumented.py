from __future__ import annotations

import logging
import time

from schemas import AdapterBootstrapStatus, LatLon, TelemetrySnapshot

from .base import FlightControllerAdapter, VideoFrame, validate_adapter_contract


class InstrumentedFlightAdapter(FlightControllerAdapter):
    _DEBUG_METHODS = {"current_leg", "get_snapshot"}

    def __init__(self, adapter: FlightControllerAdapter, logger_name: str | None = None) -> None:
        self._adapter = validate_adapter_contract(adapter)
        self._logger = logging.getLogger(logger_name or f"arrakis.adapter.{adapter.__class__.__name__.lower()}")
        self._connected = False
        self._last_error: str | None = None
        self._last_call: str | None = None
        self._last_call_ms: float | None = None

    @property
    def wrapped(self) -> FlightControllerAdapter:
        return self._adapter

    def health_status(self) -> dict[str, object]:
        bootstrap = self.bootstrap_status()
        payload = {
            "adapter": self._adapter.__class__.__name__,
            "connected": self._connected,
            "last_error": self._last_error,
            "last_call": self._last_call,
            "last_call_ms": self._last_call_ms,
            "bootstrap": bootstrap.model_dump(),
        }
        wrapped_health = getattr(self._adapter, "health_status", None)
        if callable(wrapped_health):
            payload["wrapped"] = wrapped_health()
        return payload

    def connect(self) -> None:
        self._call("connect", self._adapter.connect)
        self._connected = True

    def set_event_sink(self, callback) -> None:
        self._call("set_event_sink", self._adapter.set_event_sink, callback)

    def mission_execution_style(self) -> str:
        return self._call("mission_execution_style", self._adapter.mission_execution_style)

    def arm(self) -> None:
        self._call("arm", self._adapter.arm)

    def takeoff_multicopter(self, target_alt_m: float) -> None:
        self._call("takeoff_multicopter", self._adapter.takeoff_multicopter, target_alt_m)

    def upload_roundtrip_mission(self, route_spec: dict[str, object]) -> None:
        self._call("upload_roundtrip_mission", self._adapter.upload_roundtrip_mission, route_spec)

    def start_mission(self) -> None:
        self._call("start_mission", self._adapter.start_mission)

    def transition_to_fixedwing(self) -> None:
        self._call("transition_to_fixedwing", self._adapter.transition_to_fixedwing)

    def prepare_multicopter_recovery(self, recovery_spec: dict[str, object]) -> None:
        self._call("prepare_multicopter_recovery", self._adapter.prepare_multicopter_recovery, recovery_spec)

    def transition_to_multicopter(self) -> None:
        self._call("transition_to_multicopter", self._adapter.transition_to_multicopter)

    def return_to_home(self) -> None:
        self._call("return_to_home", self._adapter.return_to_home)

    def land_vertical(self) -> None:
        self._call("land_vertical", self._adapter.land_vertical)

    def abort(self, reason: str) -> None:
        self._call("abort", self._adapter.abort, reason)

    def reset(self) -> None:
        self._call("reset", self._adapter.reset)

    def get_snapshot(self) -> TelemetrySnapshot:
        return self._call("get_snapshot", self._adapter.get_snapshot)

    def current_leg(self) -> str:
        return self._call("current_leg", self._adapter.current_leg)

    def stream_telemetry(self, callback) -> None:
        self._call("stream_telemetry", self._adapter.stream_telemetry, callback)

    def stream_video(self, callback) -> None:
        self._call("stream_video", self._adapter.stream_video, callback)

    def get_home(self) -> LatLon:
        return self._call("get_home", self._adapter.get_home)

    def bootstrap_status(self) -> AdapterBootstrapStatus:
        return self._call("bootstrap_status", self._adapter.bootstrap_status)

    def recover_control_plane(self) -> AdapterBootstrapStatus:
        return self._call("recover_control_plane", self._adapter.recover_control_plane)

    def _call(self, name: str, fn, *args, **kwargs):
        log = self._logger.debug if name in self._DEBUG_METHODS else self._logger.info
        log("calling adapter.%s()", name)
        started = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            self._last_error = f"{type(exc).__name__}: {exc}"
            self._last_call = name
            self._last_call_ms = elapsed_ms
            self._logger.exception("adapter.%s() failed after %.1fms: %s", name, elapsed_ms, exc)
            raise
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._last_error = None
        self._last_call = name
        self._last_call_ms = elapsed_ms
        log("adapter.%s() returned in %.1fms", name, elapsed_ms)
        return result
