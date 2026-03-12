import { useEffect, useMemo, useRef, useState } from "react";
import type { FeatureCollection } from "geojson";
import maplibregl, { LngLatBounds, LngLatLike, Map, type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

type LatLon = { lat: number; lon: number };
type RoutePreview = {
  home: LatLon;
  outbound: LatLon[];
  return_path: LatLon[];
  geofence: { coordinates: LatLon[] };
  cruise_alt_m: number;
};

type Detection = {
  label: "person" | "vehicle";
  confidence: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

type StatePayload = {
  mission_phase: string;
  abort_reason: string | null;
  telemetry: {
    lat: number;
    lon: number;
    alt_m: number;
    airspeed_mps: number;
    battery_percent: number;
    flight_mode: string;
    vtol_state: string;
    home_distance_m: number;
    sim_rtf: number;
    geofence_breached: boolean;
  };
  route_progress: {
    current_leg: "takeoff" | "outbound" | "return" | "landing" | "idle";
    current_waypoint_index: number;
    outbound_total: number;
    return_total: number;
    next_waypoint: LatLon | null;
  };
  detector: {
    mode: string;
    last_inference_ms: number;
    objects_visible: number;
    recent_events: { timestamp: number; label: string; confidence: number; note: string }[];
    current_detections: Detection[];
  };
  simulator: {
    rtf: number;
    video_fps: number;
    video_latency_ms: number;
    camera_connected: boolean;
  };
  transition: {
    active: boolean;
    started_at: number | null;
    finished_at: number | null;
    duration_s: number | null;
    entry_phase: string | null;
    entry_mode: string | null;
    landing_entry_mode: string | null;
    completion: string | null;
    min_airspeed_mps: number | null;
    max_airspeed_mps: number | null;
    min_home_distance_m: number | null;
    max_alt_m: number | null;
    samples: number;
  };
  geofence: { coordinates: LatLon[] } | null;
  route_home: LatLon | null;
  outbound: LatLon[];
  return_path: LatLon[];
};

type ConfigPayload = {
  home: LatLon;
  bootstrap: {
    mission_ready: boolean;
    reason: string | null;
  };
  adapter: string;
  startup_error: string | null;
};

const API_BASE =
  import.meta.env.VITE_ARRAKIS_API_BASE?.replace(/\/$/, "") ??
  `${window.location.protocol}//${window.location.hostname}:8010`;
const WS_STATE_URL = `${API_BASE.replace(/^http/, "ws")}/ws/state`;
const MAP_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: [
        "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [
    {
      id: "osm",
      type: "raster",
      source: "osm",
    },
  ],
};

function App() {
  const mapRef = useRef<Map | null>(null);
  const mapNodeRef = useRef<HTMLDivElement | null>(null);
  const videoPanelRef = useRef<HTMLDivElement | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [home, setHome] = useState<LatLon | null>(null);
  const [waypoints, setWaypoints] = useState<LatLon[]>([]);
  const [preview, setPreview] = useState<RoutePreview | null>(null);
  const [previewReady, setPreviewReady] = useState(false);
  const [state, setState] = useState<StatePayload | null>(null);
  const [config, setConfig] = useState<ConfigPayload | null>(null);
  const [status, setStatus] = useState("Click the map to define a route.");
  const configRefreshRef = useRef<number | null>(null);
  const wsReconnectRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchConfig() {
      try {
        const response = await fetch(`${API_BASE}/api/config`);
        if (!response.ok) {
          throw new Error("config request failed");
        }
        const payload = (await response.json()) as ConfigPayload;
        if (cancelled) {
          return;
        }
        setConfig(payload);
        setHome(payload.home);
        if (payload.startup_error) {
          setStatus(`Backend degraded: ${payload.startup_error}`);
        } else if (!payload.bootstrap.mission_ready && payload.bootstrap.reason) {
          setStatus(`Vehicle bootstrap pending: ${payload.bootstrap.reason}`);
        }
      } catch {
        if (!cancelled) {
          setStatus("Backend config request failed.");
        }
      }
    }

    void fetchConfig();
    configRefreshRef.current = window.setInterval(() => {
      void fetchConfig();
    }, 5000);

    return () => {
      cancelled = true;
      if (configRefreshRef.current !== null) {
        window.clearInterval(configRefreshRef.current);
        configRefreshRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!mapNodeRef.current || !home || mapRef.current) {
      return;
    }
    const map = new maplibregl.Map({
      container: mapNodeRef.current,
      style: MAP_STYLE,
      center: [home.lon, home.lat] as LngLatLike,
      zoom: 15,
      pitch: 28,
      bearing: -8,
    });
    map.on("load", () => {
      map.addSource("route", { type: "geojson", data: emptyFeatureCollection() });
      map.addSource("return", { type: "geojson", data: emptyFeatureCollection() });
      map.addSource("geofence", { type: "geojson", data: emptyFeatureCollection() });
      map.addSource("home", { type: "geojson", data: emptyFeatureCollection() });
      map.addSource("drone", { type: "geojson", data: emptyFeatureCollection() });
      map.addSource("waypoints", { type: "geojson", data: emptyFeatureCollection() });
      map.addLayer({
        id: "geofence-fill",
        type: "fill",
        source: "geofence",
        paint: {
          "fill-color": "#f4a261",
          "fill-opacity": 0.08,
        },
      });
      map.addLayer({
        id: "geofence-line",
        type: "line",
        source: "geofence",
        paint: {
          "line-color": "#f4a261",
          "line-width": 3,
          "line-dasharray": [3, 2],
        },
      });
      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#2a9d8f", "line-width": 5 },
      });
      map.addLayer({
        id: "return-line",
        type: "line",
        source: "return",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#e76f51", "line-width": 5, "line-dasharray": [2, 2] },
      });
      map.addLayer({
        id: "waypoint-points",
        type: "circle",
        source: "waypoints",
        paint: {
          "circle-color": "#f4efe6",
          "circle-radius": 5,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#2a9d8f",
        },
      });
      map.addLayer({
        id: "home-point",
        type: "circle",
        source: "home",
        paint: {
          "circle-color": "#264653",
          "circle-radius": 8,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#fff",
        },
      });
      map.addLayer({
        id: "drone-point",
        type: "circle",
        source: "drone",
        paint: {
          "circle-color": "#fff",
          "circle-radius": 8,
          "circle-stroke-width": 3,
          "circle-stroke-color": "#1d3557",
        },
      });
      setMapReady(true);
    });
    map.on("error", () => setStatus("Map tile loading error."));
    map.on("click", (event) => {
      setWaypoints((prev) => {
        if (prev.length >= 12) {
          return prev;
        }
        return [...prev, { lat: event.lngLat.lat, lon: event.lngLat.lng }];
      });
    });
    mapRef.current = map;
    return () => {
      setMapReady(false);
      mapRef.current = null;
      map.remove();
    };
  }, [home]);

  useEffect(() => {
    const map = getUsableMap(mapRef.current, mapReady);
    if (!home || !map) {
      return;
    }
    updatePointSource(map, "home", [home]);
    updateLineSource(map, "route", waypoints);
    updatePointSource(map, "waypoints", waypoints);
    if (!previewReady && waypoints.length) {
      fitMapToPoints(map, [home, ...waypoints]);
    }
  }, [home, waypoints, mapReady, previewReady]);

  useEffect(() => {
    const map = getUsableMap(mapRef.current, mapReady);
    if (!map || !preview) {
      return;
    }
    updateLineSource(map, "route", preview.outbound);
    updateLineSource(map, "return", preview.return_path);
    updatePolygonSource(map, "geofence", preview.geofence.coordinates);
    fitMapToRoute(map, preview.home, preview.outbound, preview.return_path, preview.geofence.coordinates);
  }, [mapReady, preview]);

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | null = null;

    const scheduleReconnect = () => {
      if (disposed || wsReconnectRef.current !== null) {
        return;
      }
      wsReconnectRef.current = window.setTimeout(() => {
        wsReconnectRef.current = null;
        connectSocket();
      }, 1000);
    };

    const connectSocket = () => {
      if (disposed) {
        return;
      }
      socket = new WebSocket(WS_STATE_URL);
      socket.onopen = () => setStatus((current) => (current.includes("disconnected") ? "State stream connected." : current));
      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data) as StatePayload;
        setState(payload);
        const map = getUsableMap(mapRef.current, mapReady);
        if (map) {
          updateLineSource(map, "route", payload.outbound);
          updateLineSource(map, "return", payload.return_path);
          updatePolygonSource(map, "geofence", payload.geofence?.coordinates ?? []);
          updatePointSource(map, "drone", [{ lat: payload.telemetry.lat, lon: payload.telemetry.lon }]);
        }
      };
      socket.onerror = () => {
        setStatus("State WebSocket disconnected. Reconnecting...");
      };
      socket.onclose = () => {
        if (!disposed) {
          setStatus("State WebSocket disconnected. Reconnecting...");
          scheduleReconnect();
        }
      };
    };

    connectSocket();

    return () => {
      disposed = true;
      if (wsReconnectRef.current !== null) {
        window.clearTimeout(wsReconnectRef.current);
        wsReconnectRef.current = null;
      }
      socket?.close();
    };
  }, [mapReady]);

  async function handleSetRoute() {
    if (!home || waypoints.length < 2) {
      setStatus("Pick at least 2 waypoints.");
      return;
    }
    const response = await fetch(`${API_BASE}/api/mission/route`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ home, waypoints, cruise_alt_m: 60 }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: "Route preview failed." }));
      setStatus(payload.detail ?? "Route preview failed.");
      return;
    }
    const payload = (await response.json()) as RoutePreview;
    setPreview(payload);
    setPreviewReady(true);
    setStatus("Route ready. Start mission when you are ready.");
  }

  async function postMissionAction(path: string, nextStatus: string) {
    const response = await fetch(`${API_BASE}${path}`, { method: "POST" });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: `Request failed: ${path}` }));
      setStatus(payload.detail ?? `Request failed: ${path}`);
      return;
    }
    setStatus(nextStatus);
  }

  async function handleReset() {
    await postMissionAction("/api/mission/reset", "Mission state reset.");
    setWaypoints([]);
    setPreview(null);
    setPreviewReady(false);
  }

  const events = useMemo(() => state?.detector.recent_events ?? [], [state]);
  const detections = useMemo(() => state?.detector.current_detections ?? [], [state]);
  const missionActive =
    state != null &&
    !["IDLE", "COMPLETE", "ABORT_GEOFENCE", "ABORT_MANUAL", "RTL_BATTERY"].includes(state.mission_phase);
  const startupBlocked = Boolean(config?.startup_error);
  const bootstrapReady = Boolean(config?.bootstrap.mission_ready);
  const routeBlockedReason =
    config?.startup_error ??
    (!bootstrapReady ? config?.bootstrap.reason ?? "vehicle bootstrap not ready" : null) ??
    (missionActive ? "mission already active" : null);
  const startBlockedReason =
    config?.startup_error ??
    (!previewReady ? "set a route first" : null) ??
    (!bootstrapReady ? config?.bootstrap.reason ?? "vehicle bootstrap not ready" : null) ??
    (missionActive ? "mission already active" : null);
  const commandBlockedReason = config?.startup_error ?? (!bootstrapReady ? config?.bootstrap.reason ?? "vehicle bootstrap not ready" : null);

  return (
    <main className="shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Arrakis VTOL Mission Demo</p>
          <h1>Map a route, watch the VTOL run it, and inspect mission state live.</h1>
          <p className="lede">
            This demo isolates Arrakis mission logic from the flight controller so ArduPilot can be swapped later
            without rewriting the UI or state machine.
          </p>
        </div>
        <div className="actions">
          <button onClick={handleSetRoute} disabled={Boolean(routeBlockedReason)}>
            Set Route
          </button>
          <button onClick={() => postMissionAction("/api/mission/start", "Mission started.")} disabled={Boolean(startBlockedReason)}>
            Start Mission
          </button>
          <button
            onClick={() => postMissionAction("/api/mission/rtl", "Return-to-home requested.")}
            disabled={Boolean(commandBlockedReason)}
          >
            Return Home
          </button>
          <button
            onClick={() => postMissionAction("/api/mission/abort", "Mission abort requested.")}
            disabled={Boolean(commandBlockedReason)}
          >
            Abort
          </button>
          <button
            onClick={handleReset}
          >
            Reset
          </button>
          <div className="action-flags">
            <StatusFlag label="Adapter" tone={startupBlocked ? "danger" : "ok"} value={startupBlocked ? "degraded" : config?.adapter ?? "loading"} />
            <StatusFlag
              label="Bootstrap"
              tone={bootstrapReady ? "ok" : "warn"}
              value={bootstrapReady ? "ready" : config?.bootstrap.reason ?? "pending"}
            />
            <StatusFlag label="Mission" tone={missionActive ? "warn" : "ok"} value={missionActive ? state?.mission_phase ?? "active" : "idle"} />
          </div>
          {routeBlockedReason ? <p className="action-hint">Route locked: {routeBlockedReason}</p> : null}
          {startBlockedReason ? <p className="action-hint">Start blocked: {startBlockedReason}</p> : null}
          <p className="status">{status}</p>
        </div>
      </section>

      <section className="grid">
        <article className="panel map-panel">
          <div className="panel-header">
            <h2>Route Planner</h2>
            <p>Click the map to drop 2-12 waypoints. Geofence is generated automatically from the route.</p>
          </div>
          <div ref={mapNodeRef} className="map-node" />
        </article>

        <article className="panel video-panel">
          <div className="panel-header">
            <h2>Simulator Camera</h2>
            <p>Live MJPEG feed with detection overlay from the Arrakis backend.</p>
          </div>
          <div className="video-stage" ref={videoPanelRef}>
            <img src={`${API_BASE}/api/video/mjpeg`} alt="Simulator camera" className="video-feed" />
            <div className="overlay-layer">
              {detections.map((detection, index) => (
                <div
                  key={`${detection.label}-${index}`}
                  className={`detection detection-${detection.label}`}
                  style={{
                    left: `${detection.x1 * 100}%`,
                    top: `${detection.y1 * 100}%`,
                    width: `${(detection.x2 - detection.x1) * 100}%`,
                    height: `${(detection.y2 - detection.y1) * 100}%`,
                  }}
                >
                  <span>
                    {detection.label} {Math.round(detection.confidence * 100)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        </article>

        <article className="panel status-panel">
          <div className="panel-header">
            <h2>Mission State</h2>
            <p>Telemetry, simulator health, recovery progress, and detector events.</p>
          </div>
          <dl className="stats">
            <Metric label="Phase" value={state?.mission_phase ?? "IDLE"} />
            <Metric label="VTOL State" value={state?.telemetry.vtol_state ?? "-"} />
            <Metric label="Battery" value={state ? `${state.telemetry.battery_percent.toFixed(1)}%` : "-"} />
            <Metric label="Airspeed" value={state ? `${state.telemetry.airspeed_mps.toFixed(1)} m/s` : "-"} />
            <Metric label="Altitude" value={state ? `${state.telemetry.alt_m.toFixed(1)} m` : "-"} />
            <Metric label="RTF" value={state ? state.simulator.rtf.toFixed(2) : "-"} />
            <Metric label="Video FPS" value={state ? state.simulator.video_fps.toFixed(1) : "-"} />
            <Metric label="Video Latency" value={state ? `${state.simulator.video_latency_ms.toFixed(0)} ms` : "-"} />
            <Metric label="Leg" value={state?.route_progress.current_leg ?? "-"} />
            <Metric label="Waypoint Index" value={state ? String(state.route_progress.current_waypoint_index) : "-"} />
            <Metric label="Abort Reason" value={state?.abort_reason ?? "none"} />
            <Metric
              label="Geofence"
              value={state?.telemetry.geofence_breached ? "BREACHED" : "inside"}
              alert={Boolean(state?.telemetry.geofence_breached)}
            />
          </dl>
          <div className="event-list">
            <h3>Recovery / Landing Diagnostics</h3>
            <dl className="stats">
              <Metric label="Transition Active" value={state?.transition.active ? "yes" : "no"} />
              <Metric label="Entry Phase" value={state?.transition.entry_phase ?? "-"} />
              <Metric label="Entry Mode" value={state?.transition.entry_mode ?? "-"} />
              <Metric label="Landing Mode" value={state?.transition.landing_entry_mode ?? "-"} />
              <Metric
                label="Transition Duration"
                value={state?.transition.duration_s != null ? `${state.transition.duration_s.toFixed(1)} s` : "-"}
              />
              <Metric
                label="Min Airspeed"
                value={state?.transition.min_airspeed_mps != null ? `${state.transition.min_airspeed_mps.toFixed(1)} m/s` : "-"}
              />
              <Metric
                label="Min Home Distance"
                value={state?.transition.min_home_distance_m != null ? `${state.transition.min_home_distance_m.toFixed(1)} m` : "-"}
              />
              <Metric
                label="Max Altitude"
                value={state?.transition.max_alt_m != null ? `${state.transition.max_alt_m.toFixed(1)} m` : "-"}
              />
              <Metric label="Completion" value={state?.transition.completion ?? "-"} />
            </dl>
          </div>
          <div className="event-list">
            <h3>Recent Detector Events</h3>
            {events.length === 0 ? (
              <p className="event-empty">No detector events yet.</p>
            ) : (
              <ul>
                {events.slice().reverse().map((event, index) => (
                  <li key={`${event.timestamp}-${index}`}>
                    <strong>{event.label}</strong> {Math.round(event.confidence * 100)}% · {event.note}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </article>
      </section>
    </main>
  );
}

function Metric({ label, value, alert = false }: { label: string; value: string; alert?: boolean }) {
  return (
    <div className={`metric ${alert ? "metric-alert" : ""}`}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function StatusFlag({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "ok" | "warn" | "danger";
}) {
  return (
    <div className={`status-flag status-flag-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function emptyFeatureCollection(): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: [],
  };
}

function updateLineSource(map: Map, id: string, coords: LatLon[]) {
  const source = map.getSource(id) as maplibregl.GeoJSONSource | undefined;
  if (!source) return;
  source.setData({
    type: "FeatureCollection",
    features: coords.length
      ? [
          {
            type: "Feature",
            geometry: {
              type: "LineString",
              coordinates: coords.map((point) => [point.lon, point.lat]),
            },
            properties: {},
          },
        ]
      : [],
  });
}

function updatePolygonSource(map: Map, id: string, coords: LatLon[]) {
  const source = map.getSource(id) as maplibregl.GeoJSONSource | undefined;
  if (!source) return;
  source.setData({
    type: "FeatureCollection",
    features: coords.length
      ? [
          {
            type: "Feature",
            geometry: {
              type: "Polygon",
              coordinates: [[...coords.map((point) => [point.lon, point.lat]), [coords[0].lon, coords[0].lat]]],
            },
            properties: {},
          },
        ]
      : [],
  });
}

function updatePointSource(map: Map, id: string, coords: LatLon[]) {
  const source = map.getSource(id) as maplibregl.GeoJSONSource | undefined;
  if (!source) return;
  source.setData({
    type: "FeatureCollection",
    features: coords.map((point) => ({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [point.lon, point.lat],
      },
      properties: {},
    })),
  });
}

function getUsableMap(map: Map | null, mapReady: boolean): Map | null {
  if (!map || !mapReady) {
    return null;
  }
  if (typeof map.getSource !== "function") {
    return null;
  }
  if (typeof map.isStyleLoaded === "function" && !map.isStyleLoaded()) {
    return null;
  }
  return map;
}

function fitMapToPoints(map: Map, coords: LatLon[]) {
  if (!coords.length) return;
  const bounds = coords.reduce(
    (acc, point) => acc.extend([point.lon, point.lat]),
    new LngLatBounds([coords[0].lon, coords[0].lat], [coords[0].lon, coords[0].lat]),
  );
  map.fitBounds(bounds, { padding: 80, duration: 700, maxZoom: 16.5 });
}

function fitMapToRoute(map: Map, home: LatLon, outbound: LatLon[], returnPath: LatLon[], geofence: LatLon[]) {
  const points = [home, ...outbound, ...returnPath, ...geofence];
  fitMapToPoints(map, points);
}

export default App;
