from __future__ import annotations

import logging
from math import cos, radians

from shapely import LineString, Point

from config import GEOFENCE_HALF_WIDTH_M, HOME_BUBBLE_RADIUS_M, WAYPOINT_TURN_BUBBLE_RADIUS_M
from schemas import GeofencePolygon, LatLon, RoutePreview, RouteRequest


logger = logging.getLogger("arrakis.route_planner")


def _to_xy(home: LatLon, point: LatLon) -> tuple[float, float]:
    lat_scale = 111_320.0
    lon_scale = cos(radians(home.lat)) * 111_320.0
    return ((point.lon - home.lon) * lon_scale, (point.lat - home.lat) * lat_scale)


def _to_latlon(home: LatLon, x: float, y: float) -> LatLon:
    lat_scale = 111_320.0
    lon_scale = cos(radians(home.lat)) * 111_320.0
    return LatLon(lat=home.lat + y / lat_scale, lon=home.lon + x / lon_scale)


def build_route_preview(request: RouteRequest) -> RoutePreview:
    logger.info("Building route preview waypoints=%d cruise_alt=%.1f", len(request.waypoints), request.cruise_alt_m)
    outbound = request.waypoints
    return_path = list(reversed(request.waypoints))
    polyline = [request.home, *outbound, *return_path, request.home]
    line = LineString([_to_xy(request.home, point) for point in polyline])
    fence = line.buffer(GEOFENCE_HALF_WIDTH_M, cap_style=1, join_style=1)
    fence = fence.union(Point(0, 0).buffer(HOME_BUBBLE_RADIUS_M))
    for waypoint in outbound:
        waypoint_xy = _to_xy(request.home, waypoint)
        fence = fence.union(Point(*waypoint_xy).buffer(WAYPOINT_TURN_BUBBLE_RADIUS_M))
    coordinates = [_to_latlon(request.home, x, y) for x, y in fence.exterior.coords[:-1]]
    preview = RoutePreview(
        home=request.home,
        outbound=outbound,
        return_path=return_path,
        geofence=GeofencePolygon(coordinates=coordinates),
        cruise_alt_m=request.cruise_alt_m,
    )
    logger.info("Route preview built outbound=%d return=%d geofence_points=%d", len(preview.outbound), len(preview.return_path), len(preview.geofence.coordinates))
    return preview
