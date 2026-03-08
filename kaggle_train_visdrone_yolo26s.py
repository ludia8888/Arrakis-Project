from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml
from ultralytics import YOLO


MERGED_NAMES = {
    0: "person",
    1: "vehicle",
}

CLASS_MAP = {
    0: 0,  # pedestrian -> person
    1: 0,  # people -> person
    2: 1,  # bicycle -> vehicle
    3: 1,  # car -> vehicle
    4: 1,  # van -> vehicle
    5: 1,  # truck -> vehicle
    6: 1,  # tricycle -> vehicle
    7: 1,  # awning-tricycle -> vehicle
    8: 1,  # bus -> vehicle
    9: 1,  # motor -> vehicle
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune yolo26s.pt on VisDrone-DET with merged person/vehicle classes.")
    parser.add_argument("--data-root", type=Path, required=True, help="VisDrone root with images/ and labels/ folders.")
    parser.add_argument("--weights", type=str, default="yolo26s.pt", help="Base checkpoint path.")
    parser.add_argument("--resume-from", type=Path, help="Path to a last.pt checkpoint to resume from.")
    parser.add_argument(
        "--merged-root",
        type=Path,
        default=Path("/kaggle/working/visdrone_person_vehicle"),
        help="Writable root for generated merged dataset.",
    )
    parser.add_argument(
        "--output-yaml",
        type=Path,
        default=Path("/kaggle/working/visdrone_person_vehicle.yaml"),
        help="Generated dataset YAML path.",
    )
    parser.add_argument("--project", type=str, default="/kaggle/working/runs/visdrone", help="Ultralytics project dir.")
    parser.add_argument("--name", type=str, default="yolo26s-person-vehicle-p100", help="Ultralytics run name.")
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs.")
    parser.add_argument("--imgsz", type=int, default=1280, help="Training image size.")
    parser.add_argument("--batch", type=int, default=4, help="Batch size.")
    parser.add_argument("--workers", type=int, default=4, help="Dataloader workers.")
    parser.add_argument("--device", type=str, default="0", help="Kaggle GPU device ids, e.g. 0 or 0,1.")
    parser.add_argument("--patience", type=int, default=20, help="Early stopping patience.")
    parser.add_argument("--cache", action="store_true", help="Enable image caching.")
    parser.add_argument("--save-period", type=int, default=1, help="Save a checkpoint every N epochs.")
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


def ensure_symlink(target: Path, link_path: Path) -> None:
    if link_path.is_symlink() or link_path.exists():
        return
    link_path.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, link_path, target_is_directory=True)


def merge_label_file(source_file: Path, destination_file: Path) -> None:
    merged_lines: list[str] = []

    if source_file.exists():
        for raw_line in source_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split()
            class_id = int(float(parts[0]))
            mapped_class = CLASS_MAP.get(class_id)
            if mapped_class is None:
                continue
            merged_lines.append(" ".join([str(mapped_class), *parts[1:5]]))

    destination_file.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(merged_lines)
    if payload:
        payload += "\n"
    destination_file.write_text(payload, encoding="utf-8")


def build_merged_dataset(data_root: Path, merged_root: Path) -> Path:
    merged_root = merged_root.resolve()

    for split in ("train", "val"):
        ensure_symlink(data_root / "images" / split, merged_root / "images" / split)
        source_labels_dir = data_root / "labels" / split
        destination_labels_dir = merged_root / "labels" / split
        destination_labels_dir.mkdir(parents=True, exist_ok=True)

        for label_file in source_labels_dir.glob("*.txt"):
            merge_label_file(label_file, destination_labels_dir / label_file.name)

    test_images_dir = data_root / "images" / "test"
    if test_images_dir.exists():
        ensure_symlink(test_images_dir, merged_root / "images" / "test")

    return merged_root


def write_dataset_yaml(data_root: Path, output_yaml: Path) -> Path:
    output_yaml = output_yaml.resolve()
    payload = {
        "path": str(data_root.resolve()),
        "train": "images/train",
        "val": "images/val",
        "names": MERGED_NAMES,
    }
    if (data_root / "images" / "test").exists():
        payload["test"] = "images/test"
    output_yaml.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
    return output_yaml


def main() -> None:
    args = parse_args()
    data_root = args.data_root.resolve()

    validate_visdrone_root(data_root)
    merged_root = build_merged_dataset(data_root, args.merged_root)
    data_yaml = write_dataset_yaml(merged_root, args.output_yaml)

    print(f"Using dataset root: {data_root}")
    print(f"Generated merged dataset: {merged_root}")
    print(f"Generated YAML: {data_yaml}")
    print("Using strict split: train=images/train, val=images/val")
    print("Merged classes: 0=person, 1=vehicle")

    train_kwargs = {
        "data": str(data_yaml),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "workers": args.workers,
        "device": args.device,
        "patience": args.patience,
        "cache": args.cache,
        "save_period": args.save_period,
        "seed": args.seed,
        "project": args.project,
        "name": args.name,
        "exist_ok": args.exist_ok,
        "cos_lr": True,
        "close_mosaic": 10,
        "plots": True,
    }

    if args.resume_from:
        resume_path = args.resume_from.resolve()
        if not resume_path.exists():
            raise FileNotFoundError(f"Resume checkpoint not found: {resume_path}")
        print(f"Resuming from checkpoint: {resume_path}")
        model = YOLO(str(resume_path))
        model.train(resume=True, **train_kwargs)
    else:
        model = YOLO(args.weights)
        model.train(pretrained=True, **train_kwargs)

    save_dir = Path(model.trainer.save_dir)
    best_path = save_dir / "weights" / "best.pt"
    last_path = save_dir / "weights" / "last.pt"
    print(f"Run directory: {save_dir}")
    print(f"Best weights: {best_path}")
    print(f"Last weights: {last_path}")


if __name__ == "__main__":
    main()
