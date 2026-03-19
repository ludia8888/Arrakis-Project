from __future__ import annotations

import asyncio
import logging
import os
import resource
import time
from contextlib import asynccontextmanager
from typing import Iterator

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware

from airframe_profile import AirframeProfile, load_profile
from arrakis_core.controller import ArrakisController
from flight_adapters.ardupilot import ArduPilotAdapter
from flight_adapters.instrumented import InstrumentedFlightAdapter
from flight_adapters.mock import MockAdapter
from logging_utils import configure_logging
from schemas import RoutePreview, RouteRequest


logger = logging.getLogger("arrakis.api")


def create_adapter(profile: AirframeProfile):
    adapter_name = os.getenv("ARRAKIS_FLIGHT_ADAPTER", "mock")
    if adapter_name == "ardupilot":
        return InstrumentedFlightAdapter(ArduPilotAdapter(profile), logger_name="arrakis.adapter.ardupilot")
    return InstrumentedFlightAdapter(MockAdapter(profile), logger_name="arrakis.adapter.mock")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    profile = load_profile()
    logger.info("App startup — airframe profile=%s", profile.name)
    app.state.controller = ArrakisController(create_adapter(profile), profile)
    try:
        yield
    finally:
        logger.info("App shutdown")
        app.state.controller.shutdown()


def get_controller_from_scope(scope) -> ArrakisController:
    return scope.app.state.controller


_ALLOWED_ORIGINS = [
    "http://127.0.0.1:4173",
    "http://localhost:4173",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

_API_KEY = os.getenv("ARRAKIS_API_KEY")


class _ApiKeyMiddleware(BaseHTTPMiddleware):
    """Optional Bearer-token gate. Active only when ARRAKIS_API_KEY is set."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/api/health", "/docs", "/openapi.json"}:
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != _API_KEY:
            return JSONResponse(status_code=401, content={"detail": "invalid or missing API key"})
        return await call_next(request)


app = FastAPI(title="Arrakis VTOL Demo", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if _API_KEY:
    app.add_middleware(_ApiKeyMiddleware)
    logger.info("API key authentication enabled")


@app.get("/api/config")
def get_config(request: Request) -> dict[str, object]:
    controller = get_controller_from_scope(request)
    home = controller.adapter.get_home()
    bootstrap = controller.adapter.bootstrap_status()
    return {
        "home": home.model_dump(),
        "bootstrap": bootstrap.model_dump(),
        "adapter": os.getenv("ARRAKIS_FLIGHT_ADAPTER", "mock"),
        "airframe_profile": controller.profile.name,
        "startup_error": controller.startup_error,
    }


@app.get("/api/health")
def get_health(request: Request) -> dict[str, object]:
    controller = get_controller_from_scope(request)
    telemetry = controller.telemetry_hub.telemetry_snapshot()
    stress = controller.telemetry_hub.stress_envelope()
    detector = controller.video_service.detector_state()
    simulator = controller.video_service.simulator_state(telemetry.sim_rtf)
    bootstrap = controller.adapter.bootstrap_status()
    adapter_health = (
        controller.adapter.health_status()
        if hasattr(controller.adapter, "health_status")
        else {"adapter": controller.adapter.__class__.__name__, "connected": True}
    )
    memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    degraded = bool(
        controller.startup_error
        or not adapter_health.get("connected", True)
        or bootstrap.control_plane_fault
        or telemetry.telemetry_state != "fresh"
    )
    return {
        "status": "degraded" if degraded else "ok",
        "startup_error": controller.startup_error,
        "adapter": adapter_health,
        "bootstrap": bootstrap.model_dump(),
        "detector": {
            "enabled": detector.enabled,
            "mode": detector.mode,
            "last_inference_ms": detector.last_inference_ms,
        },
        "telemetry": {
            "last_received_at": telemetry.timestamp,
            "flight_mode": telemetry.flight_mode,
            "vtol_state": telemetry.vtol_state,
            "battery_percent": telemetry.battery_percent,
            "telemetry_age_s": telemetry.telemetry_age_s,
            "telemetry_state": telemetry.telemetry_state,
        },
        "stress": stress.model_dump(),
        "simulator": simulator.model_dump(),
        "logs": controller.log_status(),
        "memory": {
            "ru_maxrss": memory,
        },
    }


@app.post("/api/mission/route", response_model=RoutePreview)
def set_route(payload: RouteRequest, request: Request) -> RoutePreview:
    controller = get_controller_from_scope(request)
    logger.info("HTTP set_route called")
    try:
        preview = controller.build_route_preview(payload)
        return controller.set_route(preview)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/mission/start")
def start_mission(request: Request) -> dict[str, str]:
    controller = get_controller_from_scope(request)
    logger.info("HTTP start_mission called")
    try:
        controller.start_mission()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "started"}


@app.post("/api/mission/abort")
def abort_mission(request: Request) -> dict[str, str]:
    controller = get_controller_from_scope(request)
    logger.info("HTTP abort_mission called")
    controller.abort()
    return {"status": "aborting"}


@app.post("/api/mission/rtl")
def rtl_mission(request: Request) -> dict[str, str]:
    controller = get_controller_from_scope(request)
    logger.info("HTTP rtl_mission called")
    controller.rtl()
    return {"status": "rtl"}


@app.post("/api/mission/reset")
def reset_mission(request: Request) -> dict[str, str]:
    controller = get_controller_from_scope(request)
    logger.info("HTTP reset_mission called")
    controller.reset()
    return {"status": "reset"}


@app.post("/api/control/recover")
def recover_control_plane(request: Request) -> dict[str, object]:
    controller = get_controller_from_scope(request)
    logger.info("HTTP recover_control_plane called")
    try:
        bootstrap = controller.recover_control_plane()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "recovered" if not bootstrap.control_plane_fault else "faulted", "bootstrap": bootstrap.model_dump()}


@app.get("/api/state")
def get_state(request: Request) -> dict[str, object]:
    controller = get_controller_from_scope(request)
    return controller.state_payload().model_dump()


def mjpeg_stream(controller: ArrakisController) -> Iterator[bytes]:
    boundary = b"--frame"
    while True:
        frame = controller.latest_jpeg()
        if frame:
            yield boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        time.sleep(1 / 12)


@app.get("/api/video/mjpeg")
def get_mjpeg(request: Request) -> StreamingResponse:
    controller = get_controller_from_scope(request)
    return StreamingResponse(mjpeg_stream(controller), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/ws/state")
async def websocket_state(websocket: WebSocket) -> None:
    controller = get_controller_from_scope(websocket)
    logger.info("WebSocket state stream opened")
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(controller.state_payload().model_dump())
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        logger.info("WebSocket state stream disconnected")
        return
    except RuntimeError:
        logger.warning("WebSocket state stream stopped due to runtime error")
        return
