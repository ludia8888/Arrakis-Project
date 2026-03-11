from __future__ import annotations

import logging
from shapely import Point, Polygon

from config import BATTERY_RTL_THRESHOLD
from schemas import GeofencePolygon, TelemetrySnapshot


logger = logging.getLogger("arrakis.safety")


def geofence_contains(geofence: GeofencePolygon | None, telemetry: TelemetrySnapshot) -> bool:
    if geofence is None:
        return True
    polygon = Polygon([(point.lon, point.lat) for point in geofence.coordinates])
    contained = polygon.contains(Point(telemetry.lon, telemetry.lat))
    if not contained:
        logger.warning("Geofence containment failed lat=%.6f lon=%.6f", telemetry.lat, telemetry.lon)
    return contained


def should_trigger_battery_rtl(telemetry: TelemetrySnapshot) -> bool:
    triggered = telemetry.battery_percent <= BATTERY_RTL_THRESHOLD
    if triggered:
        logger.warning("Battery RTL condition met battery=%.1f threshold=%.1f", telemetry.battery_percent, BATTERY_RTL_THRESHOLD)
    return triggered
