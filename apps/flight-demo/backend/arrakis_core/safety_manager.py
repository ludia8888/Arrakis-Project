from __future__ import annotations

from shapely import Point, Polygon

from config import BATTERY_RTL_THRESHOLD
from schemas import GeofencePolygon, TelemetrySnapshot


def geofence_contains(geofence: GeofencePolygon | None, telemetry: TelemetrySnapshot) -> bool:
    if geofence is None:
        return True
    polygon = Polygon([(point.lon, point.lat) for point in geofence.coordinates])
    return polygon.contains(Point(telemetry.lon, telemetry.lat))


def should_trigger_battery_rtl(telemetry: TelemetrySnapshot) -> bool:
    return telemetry.battery_percent <= BATTERY_RTL_THRESHOLD
