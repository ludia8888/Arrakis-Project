import { useEffect, useMemo, useRef, useState } from "react";
import type { FeatureCollection } from "geojson";
import maplibregl, { LngLatLike, Map } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

type LatLon = { lat: number; lon: number };

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
    current_leg: "outbound" | "return" | "idle";
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
  geofence: { coordinates: LatLon[] } | null;
  route_home: LatLon | null;
  outbound: LatLon[];
  return_path: LatLon[];
};

const API_BASE = "http://127.0.0.1:8010";

function App() {
  const mapRef = useRef<Map | null>(null);
  const mapNodeRef = useRef<HTMLDivElement | null>(null);
  const videoPanelRef = useRef<HTMLDivElement | null>(null);
  const [home, setHome] = useState<LatLon | null>(null);
  const [waypoints, setWaypoints] = useState<LatLon[]>([]);
  const [previewReady, setPreviewReady] = useState(false);
  const [state, setState] = useState<StatePayload | null>(null);
  const [status, setStatus] = useState("Click the map to define a route.");

  useEffect(() => {
    fetch(`${API_BASE}/api/config`)
      .then((response) => response.json())
      .then((payload) => setHome(payload.home))
      .catch(() => setStatus("Backend config request failed."));
  }, []);

  useEffect(() => {
    if (!mapNodeRef.current || !home || mapRef.current) {
      return;
    }
    const map = new maplibregl.Map({
      container: mapNodeRef.current,
      style: "https://demotiles.maplibre.org/style.json",
      center: [home.lon, home.lat] as LngLatLike,
      zoom: 15,
      pitch: 40,
      bearing: -10,
    });
    map.on("load", () => {
      map.addSource("route", { type: "geojson", data: emptyFeatureCollection() });
      map.addSource("return", { type: "geojson", data: emptyFeatureCollection() });
      map.addSource("geofence", { type: "geojson", data: emptyFeatureCollection() });
      map.addSource("home", { type: "geojson", data: emptyFeatureCollection() });
      map.addSource("drone", { type: "geojson", data: emptyFeatureCollection() });
      map.addLayer({
        id: "geofence-fill",
        type: "fill",
        source: "geofence",
        paint: {
          "fill-color": "#f4a261",
          "fill-opacity": 0.14,
        },
      });
      map.addLayer({
        id: "geofence-line",
        type: "line",
        source: "geofence",
        paint: {
          "line-color": "#f4a261",
          "line-width": 2,
        },
      });
      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        paint: { "line-color": "#2a9d8f", "line-width": 4 },
      });
      map.addLayer({
        id: "return-line",
        type: "line",
        source: "return",
        paint: { "line-color": "#e76f51", "line-width": 4, "line-dasharray": [2, 2] },
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
    });
    map.on("click", (event) => {
      setWaypoints((prev) => {
        if (prev.length >= 12) {
          return prev;
        }
        return [...prev, { lat: event.lngLat.lat, lon: event.lngLat.lng }];
      });
    });
    mapRef.current = map;
    return () => map.remove();
  }, [home]);

  useEffect(() => {
    if (!home || !mapRef.current) {
      return;
    }
    updatePointSource(mapRef.current, "home", [home]);
    updateLineSource(mapRef.current, "route", waypoints);
  }, [home, waypoints]);

  useEffect(() => {
    const socket = new WebSocket("ws://127.0.0.1:8010/ws/state");
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as StatePayload;
      setState(payload);
      if (mapRef.current) {
        updateLineSource(mapRef.current, "route", payload.outbound);
        updateLineSource(mapRef.current, "return", payload.return_path);
        updatePolygonSource(mapRef.current, "geofence", payload.geofence?.coordinates ?? []);
        updatePointSource(mapRef.current, "drone", [{ lat: payload.telemetry.lat, lon: payload.telemetry.lon }]);
      }
    };
    socket.onerror = () => setStatus("State WebSocket disconnected.");
    return () => socket.close();
  }, []);

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
    setPreviewReady(false);
  }

  const events = useMemo(() => state?.detector.recent_events ?? [], [state]);
  const detections = useMemo(() => state?.detector.current_detections ?? [], [state]);

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
          <button onClick={handleSetRoute}>Set Route</button>
          <button onClick={() => postMissionAction("/api/mission/start", "Mission started.")} disabled={!previewReady}>
            Start Mission
          </button>
          <button onClick={() => postMissionAction("/api/mission/rtl", "Return-to-home requested.")}>Return Home</button>
          <button onClick={() => postMissionAction("/api/mission/abort", "Mission abort requested.")}>Abort</button>
          <button
            onClick={handleReset}
          >
            Reset
          </button>
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

export default App;
