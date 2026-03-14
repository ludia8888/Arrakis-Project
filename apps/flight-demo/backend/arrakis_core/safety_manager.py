from __future__ import annotations

import logging
from math import cos, radians

from shapely import Point, Polygon

from airframe_profile import AirframeProfile
from schemas import GeofencePolygon, MissionPhase, TelemetrySnapshot


logger = logging.getLogger("arrakis.safety")

HOME_OPERATION_PHASES = {"ARMING", "TAKEOFF_MC", "TRANSITION_FW", "TRANSITION_MC", "LANDING"}
OUTBOUND_STARTUP_MAX_MISSION_INDEX = 2


def _distance_m(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    lat_scale = 111_320.0
    lon_scale = cos(radians((lat_a + lat_b) / 2.0)) * 111_320.0
    dx = (lon_b - lon_a) * lon_scale
    dy = (lat_b - lat_a) * lat_scale
    return (dx * dx + dy * dy) ** 0.5


def geofence_contains(
    geofence: GeofencePolygon | None,
    telemetry: TelemetrySnapshot,
    phase: MissionPhase,
    route_home: tuple[float, float] | None = None,
    *,
    profile: AirframeProfile,
) -> bool:
    if geofence is None:
        return True
    polygon = Polygon([(point.lon, point.lat) for point in geofence.coordinates])
    point = Point(telemetry.lon, telemetry.lat)
    contained = polygon.covers(point)
    if contained:
        return True

    if route_home and phase in HOME_OPERATION_PHASES:
        home_lat, home_lon = route_home
        distance_m = _distance_m(home_lat, home_lon, telemetry.lat, telemetry.lon)
        if distance_m <= profile.geometry.home_operation_bubble_radius_m:
            logger.info(
                "Geofence tolerated for phase=%s lat=%.6f lon=%.6f distance=%.1fm threshold=%.1fm",
                phase,
                telemetry.lat,
                telemetry.lon,
                distance_m,
                profile.geometry.home_operation_bubble_radius_m,
            )
            return True

    if route_home and phase == "OUTBOUND" and telemetry.mission_index <= OUTBOUND_STARTUP_MAX_MISSION_INDEX:
        home_lat, home_lon = route_home
        distance_m = _distance_m(home_lat, home_lon, telemetry.lat, telemetry.lon)
        if distance_m <= profile.geometry.outbound_startup_bubble_radius_m:
            logger.info(
                "Geofence tolerated for outbound startup lat=%.6f lon=%.6f mission_idx=%d distance=%.1fm threshold=%.1fm",
                telemetry.lat,
                telemetry.lon,
                telemetry.mission_index,
                distance_m,
                profile.geometry.outbound_startup_bubble_radius_m,
            )
            return True

    logger.warning(
        "Geofence containment failed phase=%s lat=%.6f lon=%.6f route_home=%s",
        phase,
        telemetry.lat,
        telemetry.lon,
        route_home,
    )
    return False


def should_trigger_battery_rtl(telemetry: TelemetrySnapshot, *, profile: AirframeProfile) -> bool:
    threshold = profile.safety.battery_rtl_threshold_percent
    triggered = telemetry.battery_percent <= threshold
    if triggered:
        logger.warning("Battery RTL condition met battery=%.1f threshold=%.1f", telemetry.battery_percent, threshold)
    return triggered
