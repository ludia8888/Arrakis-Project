from __future__ import annotations

import asyncio
import os
import time
from typing import Iterator

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from arrakis_core.controller import ArrakisController
from arrakis_core.route_planner import build_route_preview
from flight_adapters.ardupilot import ArduPilotAdapter
from flight_adapters.mock import MockAdapter
from schemas import RoutePreview, RouteRequest


def create_adapter():
    adapter_name = os.getenv("ARRAKIS_FLIGHT_ADAPTER", "mock")
    if adapter_name == "ardupilot":
        return ArduPilotAdapter()
    return MockAdapter()


app = FastAPI(title="Arrakis VTOL Demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
controller = ArrakisController(create_adapter())


@app.get("/api/config")
def get_config() -> dict[str, object]:
    home = controller.adapter.get_home()
    return {
        "home": home.model_dump(),
        "adapter": os.getenv("ARRAKIS_FLIGHT_ADAPTER", "mock"),
    }


@app.post("/api/mission/route", response_model=RoutePreview)
def set_route(payload: RouteRequest) -> RoutePreview:
    try:
        preview = build_route_preview(payload)
        return controller.set_route(preview)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/mission/start")
def start_mission() -> dict[str, str]:
    try:
        controller.start_mission()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "started"}


@app.post("/api/mission/abort")
def abort_mission() -> dict[str, str]:
    controller.abort()
    return {"status": "aborting"}


@app.post("/api/mission/rtl")
def rtl_mission() -> dict[str, str]:
    controller.rtl()
    return {"status": "rtl"}


@app.post("/api/mission/reset")
def reset_mission() -> dict[str, str]:
    controller.reset()
    return {"status": "reset"}


@app.get("/api/state")
def get_state() -> dict[str, object]:
    return controller.state_payload().model_dump()


def mjpeg_stream() -> Iterator[bytes]:
    boundary = b"--frame"
    while True:
        frame = controller.latest_jpeg()
        if frame:
            yield boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        time.sleep(1 / 12)


@app.get("/api/video/mjpeg")
def get_mjpeg() -> StreamingResponse:
    return StreamingResponse(mjpeg_stream(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/ws/state")
async def websocket_state(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(controller.state_payload().model_dump())
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        return
    except RuntimeError:
        return
