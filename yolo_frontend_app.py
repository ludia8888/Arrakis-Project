import base64
from pathlib import Path

import cv2
import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MODEL_PATH = BASE_DIR / "yolo26s.pt"

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")

DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
MODEL = YOLO(str(MODEL_PATH))

app = FastAPI(title="YOLO26s Local Frontend")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class InferenceRequest(BaseModel):
    image: str
    conf: float = Field(default=0.25, ge=0.01, le=1.0)
    imgsz: int = Field(default=640, ge=64, le=1920)


@app.get("/")
def read_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def decode_data_url(image_data: str) -> np.ndarray:
    payload = image_data.split(",", 1)[1] if "," in image_data else image_data
    try:
        image_bytes = base64.b64decode(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image payload") from exc

    frame = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode image")
    return frame


@app.post("/api/infer")
def infer(request: InferenceRequest) -> dict[str, object]:
    frame = decode_data_url(request.image)
    height, width = frame.shape[:2]

    result = MODEL.predict(frame, conf=request.conf, imgsz=request.imgsz, verbose=False, device=DEVICE)[0]
    detections: list[dict[str, float | int | str]] = []

    if result.boxes is not None:
        names = result.names
        for box in result.boxes:
            xyxy = box.xyxy[0].tolist()
            class_id = int(box.cls.item())
            detections.append(
                {
                    "x1": float(xyxy[0]),
                    "y1": float(xyxy[1]),
                    "x2": float(xyxy[2]),
                    "y2": float(xyxy[3]),
                    "confidence": float(box.conf.item()),
                    "class_id": class_id,
                    "label": str(names[class_id]),
                }
            )

    return {
        "width": width,
        "height": height,
        "detections": detections,
    }
