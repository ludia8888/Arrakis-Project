import argparse
from pathlib import Path

import cv2
import numpy as np
from mss import mss
from ultralytics import YOLO

from model_runtime import MODEL_ENV_VAR, resolve_device, resolve_model_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run realtime YOLO26s inference from a webcam or the screen.")
    parser.add_argument(
        "--model",
        help=f"Optional checkpoint path. Defaults to {MODEL_ENV_VAR}, then ./best.pt, then ./yolo26s.pt.",
    )
    parser.add_argument("--source", choices=("webcam", "screen"), default="webcam", help="Input source type.")
    parser.add_argument("--camera", type=int, default=0, help="Webcam index to open.")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold.")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size.")
    parser.add_argument("--monitor", type=int, default=1, help="Monitor index for screen capture.")
    parser.add_argument("--select-region", action="store_true", help="Interactively select the screen region to capture.")
    parser.add_argument("--view", choices=("annotated", "split"), default="annotated", help="Preview layout.")
    parser.add_argument("--preview-scale", type=float, default=1.0, help="Preview window scale factor.")
    parser.add_argument("--left", type=int, default=0, help="Screen capture left offset in pixels.")
    parser.add_argument("--top", type=int, default=0, help="Screen capture top offset in pixels.")
    parser.add_argument("--width", type=int, default=0, help="Screen capture width. 0 uses the full monitor width.")
    parser.add_argument("--height", type=int, default=0, help="Screen capture height. 0 uses the full monitor height.")
    return parser.parse_args()


def get_monitor(screen_capture: mss, monitor_index: int) -> dict[str, int]:
    if monitor_index <= 0 or monitor_index >= len(screen_capture.monitors):
        raise ValueError(f"Invalid monitor index {monitor_index}. Available monitors: 1..{len(screen_capture.monitors) - 1}")
    return screen_capture.monitors[monitor_index]


def get_screen_region(screen_capture: mss, args: argparse.Namespace) -> dict[str, int]:
    monitor = get_monitor(screen_capture, args.monitor)
    width = args.width or (monitor["width"] - args.left)
    height = args.height or (monitor["height"] - args.top)
    return {
        "left": monitor["left"] + args.left,
        "top": monitor["top"] + args.top,
        "width": width,
        "height": height,
    }


def select_screen_region(screen_capture: mss, args: argparse.Namespace) -> dict[str, int]:
    monitor = get_monitor(screen_capture, args.monitor)
    screenshot = np.array(screen_capture.grab(monitor), dtype=np.uint8)
    frame = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
    x, y, width, height = cv2.selectROI("Select YouTube Region", frame, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow("Select YouTube Region")
    if width == 0 or height == 0:
        raise RuntimeError("Screen region selection was cancelled")
    return {
        "left": monitor["left"] + int(x),
        "top": monitor["top"] + int(y),
        "width": int(width),
        "height": int(height),
    }


def read_screen_frame(screen_capture: mss, region: dict[str, int]) -> np.ndarray:
    screenshot = screen_capture.grab(region)
    frame = np.array(screenshot, dtype=np.uint8)
    return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)


def add_label(frame: np.ndarray, text: str) -> np.ndarray:
    labeled = frame.copy()
    cv2.putText(labeled, text, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2, cv2.LINE_AA)
    return labeled


def build_preview_frame(frame: np.ndarray, annotated_frame: np.ndarray, args: argparse.Namespace) -> np.ndarray:
    if args.view == "split":
        original = add_label(frame, "Input")
        annotated = add_label(annotated_frame, "Detection")
        preview = np.hstack((original, annotated))
    else:
        preview = annotated_frame

    if args.preview_scale != 1.0:
        preview = cv2.resize(preview, None, fx=args.preview_scale, fy=args.preview_scale, interpolation=cv2.INTER_AREA)
    return preview


def place_preview_window(
    window_name: str,
    preview_frame: np.ndarray,
    region: dict[str, int],
    monitor: dict[str, int],
) -> None:
    preview_height, preview_width = preview_frame.shape[:2]
    x = region["left"] + region["width"] + 20
    max_x = monitor["left"] + monitor["width"] - preview_width
    if x > max_x:
        x = max(monitor["left"], region["left"] - preview_width - 20)

    y = min(region["top"], monitor["top"] + monitor["height"] - preview_height)
    y = max(monitor["top"], y)
    cv2.moveWindow(window_name, int(x), int(y))


def main() -> None:
    args = parse_args()
    model_path = resolve_model_path(args.model)
    device = resolve_device()
    model = YOLO(str(model_path))
    print(f"Loaded realtime model: {model_path} on {device}")
    capture = None
    screen_capture = None
    region = None
    monitor = None

    if args.source == "webcam":
        capture = cv2.VideoCapture(args.camera)
        if not capture.isOpened():
            raise RuntimeError(f"Could not open webcam index {args.camera}")
    else:
        screen_capture = mss()
        monitor = get_monitor(screen_capture, args.monitor)
        region = select_screen_region(screen_capture, args) if args.select_region else get_screen_region(screen_capture, args)

    window_name = "YOLO26s Realtime"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    window_placed = False

    try:
        while True:
            if args.source == "webcam":
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("Failed to read a frame from the webcam")
            else:
                frame = read_screen_frame(screen_capture, region)

            result = model.predict(frame, conf=args.conf, imgsz=args.imgsz, verbose=False, device=device)[0]
            annotated_frame = result.plot()
            preview_frame = build_preview_frame(frame, annotated_frame, args)

            cv2.imshow(window_name, preview_frame)
            if args.source == "screen" and not window_placed:
                place_preview_window(window_name, preview_frame, region, monitor)
                window_placed = True
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        if capture is not None:
            capture.release()
        if screen_capture is not None:
            screen_capture.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
