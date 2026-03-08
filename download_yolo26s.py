from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    model_path = Path("yolo26s.pt")
    model = YOLO(str(model_path))
    resolved_path = Path(getattr(model, "ckpt_path", model_path)).resolve()
    print(f"Model ready: {resolved_path}")


if __name__ == "__main__":
    main()
