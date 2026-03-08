from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from ultralytics import YOLO


VISDRONE_NAMES = {
    0: "pedestrian",
    1: "people",
    2: "bicycle",
    3: "car",
    4: "van",
    5: "truck",
    6: "tricycle",
    7: "awning-tricycle",
    8: "bus",
    9: "motor",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune yolo26s.pt on VisDrone-DET train+val from Kaggle.")
    parser.add_argument("--data-root", type=Path, required=True, help="VisDrone root with images/ and labels/ folders.")
    parser.add_argument("--weights", type=str, default="yolo26s.pt", help="Base checkpoint path.")
    parser.add_argument("--output-yaml", type=Path, default=Path("visdrone_det_trainval.yaml"), help="Generated dataset YAML path.")
    parser.add_argument("--project", type=str, default="/kaggle/working/runs/visdrone", help="Ultralytics project dir.")
    parser.add_argument("--name", type=str, default="yolo26s-trainval-p100", help="Ultralytics run name.")
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs.")
    parser.add_argument("--imgsz", type=int, default=1280, help="Training image size.")
    parser.add_argument("--batch", type=int, default=4, help="Batch size.")
    parser.add_argument("--workers", type=int, default=4, help="Dataloader workers.")
    parser.add_argument("--device", type=str, default="0", help="Kaggle GPU device ids, e.g. 0 or 0,1.")
    parser.add_argument("--patience", type=int, default=20, help="Early stopping patience.")
    parser.add_argument("--cache", action="store_true", help="Enable image caching.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--exist-ok", action="store_true", help="Reuse an existing run directory.")
    return parser.parse_args()


def validate_visdrone_root(data_root: Path) -> None:
    required_paths = [
        data_root / "images" / "train",
        data_root / "images" / "val",
        data_root / "labels" / "train",
        data_root / "labels" / "val",
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        joined = "\n".join(missing)
        raise FileNotFoundError(f"VisDrone root is missing required paths:\n{joined}")


def write_trainval_yaml(data_root: Path, output_yaml: Path) -> Path:
    output_yaml = output_yaml.resolve()
    payload = {
        "path": str(data_root.resolve()),
        "train": ["images/train", "images/val"],
        "val": "images/val",
        "test": "images/test",
        "names": VISDRONE_NAMES,
    }
    output_yaml.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
    return output_yaml


def main() -> None:
    args = parse_args()
    data_root = args.data_root.resolve()

    validate_visdrone_root(data_root)
    data_yaml = write_trainval_yaml(data_root, args.output_yaml)

    print(f"Using dataset root: {data_root}")
    print(f"Generated YAML: {data_yaml}")
    print("Note: train+val fine-tuning reuses val for validation, so reported val metrics will be optimistic.")

    model = YOLO(args.weights)
    results = model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        device=args.device,
        patience=args.patience,
        cache=args.cache,
        seed=args.seed,
        project=args.project,
        name=args.name,
        exist_ok=args.exist_ok,
        cos_lr=True,
        close_mosaic=10,
        pretrained=True,
        plots=True,
    )

    best_path = Path(results.save_dir) / "weights" / "best.pt"
    last_path = Path(results.save_dir) / "weights" / "last.pt"
    print(f"Best weights: {best_path}")
    print(f"Last weights: {last_path}")


if __name__ == "__main__":
    main()
