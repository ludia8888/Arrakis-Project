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
  stress: {
    level: "nominal" | "elevated" | "severe" | "critical";
    overall_score: number;
    wind_load_score: number;
    gps_degradation_score: number;
    sensor_noise_score: number;
    progress_stall_score: number;
    reasons: string[];
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
  const prevMapDataRef = useRef<string>("");

  // ── Config polling ──
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

  // ── Map initialization ──
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
          "fill-color": "#d4a24e",
          "fill-opacity": 0.06,
        },
      });
      map.addLayer({
        id: "geofence-line",
        type: "line",
        source: "geofence",
        paint: {
          "line-color": "#d4a24e",
          "line-width": 2,
          "line-dasharray": [4, 3],
        },
      });
      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#25b89a", "line-width": 4 },
      });
      map.addLayer({
        id: "return-line",
        type: "line",
        source: "return",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#d94545", "line-width": 3, "line-dasharray": [3, 2] },
      });
      map.addLayer({
        id: "waypoint-points",
        type: "circle",
        source: "waypoints",
        paint: {
          "circle-color": "#e4ddd0",
          "circle-radius": 5,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#25b89a",
        },
      });
      map.addLayer({
        id: "home-point",
        type: "circle",
        source: "home",
        paint: {
          "circle-color": "#d4a24e",
          "circle-radius": 9,
          "circle-stroke-width": 3,
          "circle-stroke-color": "#0a0f14",
        },
      });
      map.addLayer({
        id: "drone-point",
        type: "circle",
        source: "drone",
        paint: {
          "circle-color": "#fff",
          "circle-radius": 7,
          "circle-stroke-width": 3,
          "circle-stroke-color": "#0a0f14",
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

  // ── Update map sources on waypoint/home change ──
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

  // ── Update map on preview change ──
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

  // ── WebSocket state stream ──
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
          // Drone position: always update (changes every frame)
          updatePointSource(map, "drone", [{ lat: payload.telemetry.lat, lon: payload.telemetry.lon }]);

          // Route/return/geofence: only update when data actually changes
          const fenceCoords = payload.geofence?.coordinates ?? [];
          const mapDataKey = `${payload.outbound.length}|${payload.return_path.length}|${fenceCoords.length}|${payload.outbound[0]?.lat ?? 0}|${payload.return_path[0]?.lat ?? 0}`;
          if (mapDataKey !== prevMapDataRef.current) {
            prevMapDataRef.current = mapDataKey;
            updateLineSource(map, "route", payload.outbound);
            updateLineSource(map, "return", payload.return_path);
            updatePolygonSource(map, "geofence", fenceCoords);
          }
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

  // ── Mission actions ──
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

  // ── Derived state ──
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

  const phaseClass = missionActive
    ? state?.mission_phase.startsWith("ABORT") || state?.mission_phase.startsWith("RTL")
      ? state?.mission_phase.startsWith("RTL")
        ? "phase-rtl"
        : "phase-abort"
      : "phase-active"
    : "phase-idle";

  return (
    <div className="gcs">
      {/* ═══ TOP BAR ═══ */}
      <header className="topbar">
        <div className="brand">
          <span className="logo-mark">A</span>
          <span className="logo-text">ARRAKIS</span>
          <span className="logo-sub">GCS</span>
        </div>

        <div className="system-indicators">
          <Indicator
            label="Adapter"
            value={startupBlocked ? "DEGRADED" : config?.adapter ?? "..."}
            tone={startupBlocked ? "danger" : "ok"}
          />
          <Indicator
            label="Bootstrap"
            value={bootstrapReady ? "READY" : config?.bootstrap.reason ?? "PENDING"}
            tone={bootstrapReady ? "ok" : "warn"}
          />
          <Indicator
            label="Mission"
            value={missionActive ? state?.mission_phase ?? "ACTIVE" : "IDLE"}
            tone={missionActive ? "warn" : "ok"}
          />
        </div>

        <div className="topbar-right">
          <span className={`phase-badge ${phaseClass}`}>
            {state?.mission_phase ?? "IDLE"}
          </span>
          <Clock />
        </div>
      </header>

      {/* ═══ WORKSPACE ═══ */}
      <div className="workspace">
        {/* ── Left Panel: Controls + Telemetry ── */}
        <aside className="panel-left">
          {/* Mission Controls */}
          <div className="panel-section">
            <div className="section-header">Mission Control</div>
            <div className="control-grid">
              <button className="btn-primary" onClick={handleSetRoute} disabled={Boolean(routeBlockedReason)}>
                Set Route
              </button>
              <button
                className="btn-primary"
                onClick={() => postMissionAction("/api/mission/start", "Mission started.")}
                disabled={Boolean(startBlockedReason)}
              >
                Start Mission
              </button>
              <button
                className="btn-warn"
                onClick={() => postMissionAction("/api/mission/rtl", "Return-to-home requested.")}
                disabled={Boolean(commandBlockedReason)}
              >
                Return Home
              </button>
              <button
                className="btn-danger"
                onClick={() => postMissionAction("/api/mission/abort", "Mission abort requested.")}
                disabled={Boolean(commandBlockedReason)}
              >
                Abort
              </button>
              <button className="btn-reset" onClick={handleReset}>
                Reset
              </button>
            </div>
            <div className="blocked-hints">
              {routeBlockedReason && <span className="blocked-hint">Route: {routeBlockedReason}</span>}
              {startBlockedReason && <span className="blocked-hint">Start: {startBlockedReason}</span>}
            </div>
            <div className="status-message">{status}</div>
          </div>

          {/* Flight Telemetry */}
          <div className="panel-section">
            <div className="section-header">Flight Telemetry</div>
            <div className="telem-grid">
              <TelemetryCell label="Phase" value={state?.mission_phase ?? "IDLE"} />
              <TelemetryCell label="VTOL State" value={state?.telemetry.vtol_state ?? "-"} />
              <TelemetryCell label="Battery" value={state ? `${state.telemetry.battery_percent.toFixed(1)}%` : "-"} />
              <TelemetryCell label="Airspeed" value={state ? `${state.telemetry.airspeed_mps.toFixed(1)} m/s` : "-"} />
              <TelemetryCell label="Altitude" value={state ? `${state.telemetry.alt_m.toFixed(1)} m` : "-"} />
              <TelemetryCell label="Home Dist" value={state ? `${state.telemetry.home_distance_m.toFixed(0)} m` : "-"} />
              <TelemetryCell
                label="Geofence"
                value={state?.telemetry.geofence_breached ? "BREACHED" : "Inside"}
                alert={Boolean(state?.telemetry.geofence_breached)}
              />
              <TelemetryCell label="Leg" value={state?.route_progress.current_leg ?? "-"} />
              <TelemetryCell label="WP Index" value={state ? String(state.route_progress.current_waypoint_index) : "-"} />
              <TelemetryCell label="Abort" value={state?.abort_reason ?? "none"} />
            </div>
          </div>

          {/* Recovery Diagnostics */}
          <div className="panel-section">
            <div className="section-header">Recovery Diagnostics</div>
            <div className="transition-grid">
              <TransitionCell label="Active" value={state?.transition.active ? "YES" : "NO"} />
              <TransitionCell label="Entry Phase" value={state?.transition.entry_phase ?? "-"} />
              <TransitionCell label="Entry Mode" value={state?.transition.entry_mode ?? "-"} />
              <TransitionCell label="Landing" value={state?.transition.landing_entry_mode ?? "-"} />
              <TransitionCell
                label="Duration"
                value={state?.transition.duration_s != null ? `${state.transition.duration_s.toFixed(1)}s` : "-"}
              />
              <TransitionCell
                label="Min Speed"
                value={state?.transition.min_airspeed_mps != null ? `${state.transition.min_airspeed_mps.toFixed(1)}` : "-"}
              />
              <TransitionCell
                label="Min Dist"
                value={state?.transition.min_home_distance_m != null ? `${state.transition.min_home_distance_m.toFixed(0)}m` : "-"}
              />
              <TransitionCell
                label="Max Alt"
                value={state?.transition.max_alt_m != null ? `${state.transition.max_alt_m.toFixed(1)}m` : "-"}
              />
              <TransitionCell label="Completion" value={state?.transition.completion ?? "-"} />
            </div>
          </div>

          <div className="panel-section">
            <div className="section-header">Stress Envelope</div>
            <div className="transition-grid">
              <TransitionCell label="Level" value={state?.stress.level ?? "-"} />
              <TransitionCell
                label="Overall"
                value={state?.stress ? state.stress.overall_score.toFixed(2) : "-"}
              />
              <TransitionCell
                label="Wind"
                value={state?.stress ? state.stress.wind_load_score.toFixed(2) : "-"}
              />
              <TransitionCell
                label="GPS"
                value={state?.stress ? state.stress.gps_degradation_score.toFixed(2) : "-"}
              />
              <TransitionCell
                label="Sensor"
                value={state?.stress ? state.stress.sensor_noise_score.toFixed(2) : "-"}
              />
              <TransitionCell
                label="Stall"
                value={state?.stress ? state.stress.progress_stall_score.toFixed(2) : "-"}
              />
              <TransitionCell
                label="Reasons"
                value={state?.stress?.reasons.length ? state.stress.reasons.join(", ") : "-"}
              />
            </div>
          </div>
        </aside>

        {/* ── Center: Map ── */}
        <div className="map-container">
          <div ref={mapNodeRef} className="map-canvas" />
          {waypoints.length > 0 && (
            <div className="map-waypoint-count">
              WP {waypoints.length}/12
            </div>
          )}
          {!previewReady && waypoints.length < 2 && (
            <div className="map-hint">Click map to place waypoints</div>
          )}
        </div>

        {/* ── Right Panel: Camera + Events ── */}
        <aside className="panel-right">
          {/* Camera Feed */}
          <div className="camera-section">
            <div className="camera-header">
              <h3>Camera Feed</h3>
              <span className="cam-live">LIVE</span>
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
            <div className="camera-stats">
              <div className="cam-stat">
                <span className="cam-stat-label">FPS</span>
                <span className="cam-stat-value">{state ? state.simulator.video_fps.toFixed(1) : "-"}</span>
              </div>
              <div className="cam-stat">
                <span className="cam-stat-label">Latency</span>
                <span className="cam-stat-value">{state ? `${state.simulator.video_latency_ms.toFixed(0)}ms` : "-"}</span>
              </div>
              <div className="cam-stat">
                <span className="cam-stat-label">Objects</span>
                <span className="cam-stat-value">{state ? state.detector.objects_visible : "-"}</span>
              </div>
              <div className="cam-stat">
                <span className="cam-stat-label">Inference</span>
                <span className="cam-stat-value">{state ? `${state.detector.last_inference_ms.toFixed(0)}ms` : "-"}</span>
              </div>
            </div>
          </div>

          {/* AI Detection Events */}
          <div className="events-section">
            <div className="events-header">
              AI Detections
              {events.length > 0 && <span className="event-count">{events.length}</span>}
            </div>
            {events.length === 0 ? (
              <p className="events-empty">No detector events yet.</p>
            ) : (
              <ul className="event-list-items">
                {events
                  .slice()
                  .reverse()
                  .map((event, index) => (
                    <li key={`${event.timestamp}-${index}`} className="event-item">
                      <span className={`event-label event-label-${event.label}`}>{event.label}</span>
                      <span className="event-note">{event.note}</span>
                      <span className="event-confidence">{Math.round(event.confidence * 100)}%</span>
                    </li>
                  ))}
              </ul>
            )}
          </div>
        </aside>
      </div>

      {/* ═══ BOTTOM TELEMETRY STRIP ═══ */}
      <footer className="telemetry-strip">
        <StripItem label="Phase" value={state?.mission_phase ?? "IDLE"} />
        <StripItem label="BAT" value={state ? `${state.telemetry.battery_percent.toFixed(1)}%` : "-"}
          tone={state && state.telemetry.battery_percent < 30 ? "alert" : undefined} />
        <StripItem label="ALT" value={state ? `${state.telemetry.alt_m.toFixed(1)}m` : "-"} />
        <StripItem label="SPD" value={state ? `${state.telemetry.airspeed_mps.toFixed(1)}m/s` : "-"} />
        <StripItem label="DIST" value={state ? `${state.telemetry.home_distance_m.toFixed(0)}m` : "-"} />
        <StripItem label="LEG" value={state?.route_progress.current_leg ?? "-"} />
        <StripItem
          label="FENCE"
          value={state?.telemetry.geofence_breached ? "BREACHED" : "OK"}
          tone={state?.telemetry.geofence_breached ? "alert" : "ok"}
        />
        <StripItem label="RTF" value={state ? state.simulator.rtf.toFixed(2) : "-"} />
        <StripItem
          label="STRESS"
          value={state?.stress.level ?? "-"}
          tone={
            state?.stress.level === "critical"
              ? "alert"
              : state?.stress.level === "severe" || state?.stress.level === "elevated"
                ? "warn"
                : "ok"
          }
        />
        <StripItem label="VTOL" value={state?.telemetry.vtol_state ?? "-"} />
        <StripItem label="MODE" value={state?.telemetry.flight_mode ?? "-"} />
      </footer>
    </div>
  );
}

/* ── Sub-components ── */

function Indicator({ label, value, tone }: { label: string; value: string; tone: "ok" | "warn" | "danger" }) {
  return (
    <div className={`indicator indicator-${tone}`}>
      <span className="indicator-dot" />
      <span className="indicator-label">{label}</span>
      <span className="indicator-value">{value}</span>
    </div>
  );
}

function TelemetryCell({ label, value, alert = false }: { label: string; value: string; alert?: boolean }) {
  return (
    <div className={`telem-cell${alert ? " telem-cell-alert" : ""}`}>
      <span className="telem-label">{label}</span>
      <span className="telem-value">{value}</span>
    </div>
  );
}

function TransitionCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="transition-cell">
      <span className="transition-label">{label}</span>
      <span className="transition-value">{value}</span>
    </div>
  );
}

function StripItem({ label, value, tone }: { label: string; value: string; tone?: "ok" | "alert" | "warn" }) {
  const cls = tone ? ` strip-value-${tone}` : "";
  return (
    <div className="strip-item">
      <span className="strip-label">{label}</span>
      <span className={`strip-value${cls}`}>{value}</span>
    </div>
  );
}

function Clock() {
  const [time, setTime] = useState(formatTime());
  useEffect(() => {
    const id = window.setInterval(() => setTime(formatTime()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return <span className="clock">{time}</span>;
}

function formatTime() {
  const now = new Date();
  return now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/* ── Map helpers ── */

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
