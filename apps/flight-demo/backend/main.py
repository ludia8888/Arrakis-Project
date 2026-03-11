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
from fastapi.responses import StreamingResponse

from arrakis_core.controller import ArrakisController
from flight_adapters.ardupilot import ArduPilotAdapter
from flight_adapters.instrumented import InstrumentedFlightAdapter
from flight_adapters.mock import MockAdapter
from logging_utils import configure_logging
from schemas import RoutePreview, RouteRequest


logger = logging.getLogger("arrakis.api")


def create_adapter():
    adapter_name = os.getenv("ARRAKIS_FLIGHT_ADAPTER", "mock")
    if adapter_name == "ardupilot":
        return InstrumentedFlightAdapter(ArduPilotAdapter(), logger_name="arrakis.adapter.ardupilot")
    return InstrumentedFlightAdapter(MockAdapter(), logger_name="arrakis.adapter.mock")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("App startup")
    app.state.controller = ArrakisController(create_adapter())
    try:
        yield
    finally:
        logger.info("App shutdown")
        app.state.controller.shutdown()


def get_controller_from_scope(scope) -> ArrakisController:
    return scope.app.state.controller


app = FastAPI(title="Arrakis VTOL Demo", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/config")
def get_config(request: Request) -> dict[str, object]:
    controller = get_controller_from_scope(request)
    home = controller.adapter.get_home()
    bootstrap = controller.adapter.bootstrap_status()
    return {
        "home": home.model_dump(),
        "bootstrap": bootstrap.model_dump(),
        "adapter": os.getenv("ARRAKIS_FLIGHT_ADAPTER", "mock"),
    }


@app.get("/api/health")
def get_health(request: Request) -> dict[str, object]:
    controller = get_controller_from_scope(request)
    telemetry = controller.telemetry_hub.telemetry_snapshot()
    detector = controller.video_service.detector_state()
    simulator = controller.video_service.simulator_state(telemetry.sim_rtf)
    adapter_health = (
        controller.adapter.health_status()
        if hasattr(controller.adapter, "health_status")
        else {"adapter": controller.adapter.__class__.__name__, "connected": True}
    )
    memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "status": "ok",
        "adapter": adapter_health,
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
        },
        "simulator": simulator.model_dump(),
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
