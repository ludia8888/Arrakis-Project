from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


MissionPhase = Literal[
    "IDLE",
    "ARMING",
    "TAKEOFF_MC",
    "TRANSITION_FW",
    "OUTBOUND",
    "RETURN",
    "PRE_MC_RECOVERY",
    "TRANSITION_MC",
    "LANDING",
    "RTL_BATTERY",
    "ABORT_GEOFENCE",
    "ABORT_MANUAL",
    "COMPLETE",
]


class LatLon(BaseModel):
    lat: float
    lon: float


class GeofencePolygon(BaseModel):
    coordinates: list[LatLon]


class RouteRequest(BaseModel):
    home: LatLon
    waypoints: list[LatLon] = Field(min_length=2, max_length=12)
    cruise_alt_m: float = 60.0


class RoutePreview(BaseModel):
    home: LatLon
    outbound: list[LatLon]
    return_path: list[LatLon]
    geofence: GeofencePolygon
    cruise_alt_m: float


class RecoverySpec(BaseModel):
    recovery_center: LatLon
    target_alt_m: float
    loiter_radius_m: float
    speed_threshold_mps: float
    home_distance_threshold_m: float
    altitude_deviation_m: float
    dwell_seconds: float
    timeout_seconds: float


class AdapterBootstrapStatus(BaseModel):
    connected: bool
    heartbeat_received: bool
    telemetry_fresh: bool
    mode_ready: bool
    position_ready: bool
    home_ready: bool
    mission_ready: bool
    last_telemetry_at: float | None
    reason: str | None


class TelemetrySnapshot(BaseModel):
    timestamp: float
    lat: float
    lon: float
    alt_m: float
    airspeed_mps: float
    groundspeed_mps: float
    battery_percent: float
    armed: bool
    flight_mode: str
    vtol_state: str
    mission_index: int
    home_distance_m: float
    geofence_breached: bool
    sim_rtf: float
    telemetry_fresh: bool = False
    mode_valid: bool = False
    position_valid: bool = False
    home_valid: bool = False


class DetectionBox(BaseModel):
    label: Literal["person", "vehicle"]
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


class DetectorEvent(BaseModel):
    timestamp: float
    label: Literal["person", "vehicle"]
    confidence: float
    note: str


class RouteProgress(BaseModel):
    outbound_total: int
    return_total: int
    current_leg: Literal["takeoff", "outbound", "return", "idle"]
    current_waypoint_index: int
    next_waypoint: LatLon | None


class DetectorState(BaseModel):
    enabled: bool
    mode: str
    last_inference_ms: float
    objects_visible: int
    recent_events: list[DetectorEvent]
    current_detections: list[DetectionBox]


class SimulatorState(BaseModel):
    connected: bool
    camera_connected: bool
    rtf: float
    video_fps: float
    video_latency_ms: float


class StatePayload(BaseModel):
    timestamp: float
    mission_phase: MissionPhase
    abort_reason: str | None
    telemetry: TelemetrySnapshot
    route_progress: RouteProgress
    detector: DetectorState
    simulator: SimulatorState
    geofence: GeofencePolygon | None
    route_home: LatLon | None
    outbound: list[LatLon]
    return_path: list[LatLon]
