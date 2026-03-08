from __future__ import annotations

import argparse
import os
import shutil
import zipfile
from pathlib import Path

import yaml
from PIL import Image
from ultralytics import YOLO


KAGGLE_INPUT_ROOT = Path("/kaggle/input")
KAGGLE_WORKING_ROOT = Path("/kaggle/working")
RAW_TRAIN_DIR_NAME = "VisDrone2019-DET-train"
RAW_VAL_DIR_NAME = "VisDrone2019-DET-val"
RAW_TEST_DIR_NAMES = ("VisDrone2019-DET-test-dev", "VisDrone2019-DET-test-challenge")
ZIP_NAMES = {
    "train": f"{RAW_TRAIN_DIR_NAME}.zip",
    "val": f"{RAW_VAL_DIR_NAME}.zip",
    "test": "VisDrone2019-DET-test-dev.zip",
}
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp")

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
    parser.add_argument(
        "--data-root",
        type=Path,
        help="VisDrone root with images/ and labels/ folders. Optional on Kaggle: the script can auto-detect input data.",
    )
    parser.add_argument("--weights", type=str, default="yolo26s.pt", help="Base checkpoint path.")
    parser.add_argument("--resume-from", type=Path, help="Path to a last.pt checkpoint to resume from.")
    parser.add_argument(
        "--merged-root",
        type=Path,
        default=KAGGLE_WORKING_ROOT / "visdrone_person_vehicle",
        help="Writable root for generated merged dataset.",
    )
    parser.add_argument(
        "--output-yaml",
        type=Path,
        default=KAGGLE_WORKING_ROOT / "visdrone_person_vehicle.yaml",
        help="Generated dataset YAML path.",
    )
    parser.add_argument(
        "--converted-yolo-root",
        type=Path,
        default=KAGGLE_WORKING_ROOT / "visdrone_yolo",
        help="Writable root for auto-converted YOLO VisDrone data when raw Kaggle inputs are attached.",
    )
    parser.add_argument("--project", type=str, default=str(KAGGLE_WORKING_ROOT / "runs" / "visdrone"), help="Ultralytics project dir.")
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


def running_on_kaggle() -> bool:
    return KAGGLE_INPUT_ROOT.exists() and KAGGLE_WORKING_ROOT.exists()


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


def count_image_files(images_dir: Path) -> int:
    return sum(1 for path in images_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)


def collect_split_counts(data_root: Path) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for split in ("train", "val"):
        images_dir = data_root / "images" / split
        labels_dir = data_root / "labels" / split
        counts[split] = {
            "images": count_image_files(images_dir),
            "labels": len(list(labels_dir.glob("*.txt"))),
        }
    return counts


def print_split_counts(title: str, counts: dict[str, dict[str, int]]) -> None:
    print(title)
    for split, split_counts in counts.items():
        print(f"  {split}: images={split_counts['images']}, labels={split_counts['labels']}")


def validate_nonempty_training_data(data_root: Path, dataset_name: str) -> dict[str, dict[str, int]]:
    counts = collect_split_counts(data_root)
    print_split_counts(f"{dataset_name} counts:", counts)

    missing_images = [split for split, split_counts in counts.items() if split_counts["images"] == 0]
    missing_labels = [split for split, split_counts in counts.items() if split_counts["labels"] == 0]

    if missing_images or missing_labels:
        problems: list[str] = []
        if missing_images:
            problems.append(f"no images in splits: {', '.join(missing_images)}")
        if missing_labels:
            problems.append(f"no label txt files in splits: {', '.join(missing_labels)}")
        raise RuntimeError(
            f"{dataset_name} is not usable for training ({'; '.join(problems)}). "
            "Stopping before YOLO training so an invalid run does not continue."
        )
    return counts


def ensure_symlink(target: Path, link_path: Path) -> None:
    if link_path.is_symlink():
        try:
            if link_path.resolve() == target.resolve():
                return
        except FileNotFoundError:
            pass
        link_path.unlink()
    elif link_path.exists():
        remove_path(link_path)
    link_path.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, link_path, target_is_directory=True)


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def prepare_merged_root(merged_root: Path) -> None:
    merged_root.mkdir(parents=True, exist_ok=True)
    remove_path(merged_root / "images")
    remove_path(merged_root / "labels")


def classify_visdrone_root(root: Path) -> str | None:
    if (root / "images" / "train").exists() and (root / "labels" / "train").exists():
        return "yolo"
    if (root / RAW_TRAIN_DIR_NAME).exists() and (root / RAW_VAL_DIR_NAME).exists():
        return "raw_dir"
    if (root / ZIP_NAMES["train"]).exists() and (root / ZIP_NAMES["val"]).exists():
        return "raw_zip"
    return None


def resolve_visdrone_input_root(search_root: Path) -> tuple[str, Path]:
    if not search_root.exists():
        raise FileNotFoundError(f"Search root does not exist: {search_root}")

    candidates: list[Path] = []
    for current_root, dirnames, _ in os.walk(search_root):
        current_path = Path(current_root)
        candidates.append(current_path)

        # Once a candidate already looks like a VisDrone root, stop walking deeper into that branch.
        if classify_visdrone_root(current_path):
            dirnames[:] = []

    for candidate in candidates:
        detected = classify_visdrone_root(candidate)
        if detected:
            return detected, candidate

    raise FileNotFoundError(
        "Could not detect VisDrone data.\n"
        "Expected one of:\n"
        "1) YOLO format: images/train + labels/train\n"
        "2) Raw dirs: VisDrone2019-DET-train + VisDrone2019-DET-val\n"
        "3) Raw zip files: VisDrone2019-DET-train.zip + VisDrone2019-DET-val.zip\n"
        "Attach a VisDrone dataset to the Kaggle notebook or pass --data-root explicitly."
    )


def prepare_clean_dir(path: Path) -> Path:
    remove_path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def find_image_for_annotation(images_dir: Path, stem: str) -> Path | None:
    for suffix in IMAGE_SUFFIXES:
        candidate = images_dir / f"{stem}{suffix}"
        if candidate.exists():
            return candidate
    return None


def convert_visdrone_det_split(source_dir: Path, split_name: str, out_root: Path) -> None:
    images_link = out_root / "images" / split_name
    labels_dir = out_root / "labels" / split_name
    ensure_symlink(source_dir / "images", images_link)
    labels_dir.mkdir(parents=True, exist_ok=True)

    for ann_file in sorted((source_dir / "annotations").glob("*.txt")):
        image_path = find_image_for_annotation(images_link, ann_file.stem)
        if image_path is None:
            continue

        with Image.open(image_path) as image:
            image_width, image_height = image.size

        dw = 1.0 / image_width
        dh = 1.0 / image_height
        yolo_lines: list[str] = []

        for raw_line in ann_file.read_text(encoding="utf-8").splitlines():
            row = [value.strip() for value in raw_line.strip().split(",")]
            if len(row) < 6 or row[4] == "0":
                continue

            x, y, w, h = map(int, row[:4])
            class_id = int(row[5]) - 1
            if class_id < 0 or class_id > 9:
                continue

            x_center = (x + w / 2) * dw
            y_center = (y + h / 2) * dh
            w_norm = w * dw
            h_norm = h * dh
            yolo_lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}")

        payload = "\n".join(yolo_lines)
        if payload:
            payload += "\n"
        (labels_dir / ann_file.name).write_text(payload, encoding="utf-8")


def prepare_yolo_data_root(args: argparse.Namespace) -> Path:
    if args.data_root:
        data_root = args.data_root.resolve()
        validate_visdrone_root(data_root)
        return data_root

    if not running_on_kaggle():
        raise FileNotFoundError("Pass --data-root when running outside Kaggle.")

    detected_format, detected_root = resolve_visdrone_input_root(KAGGLE_INPUT_ROOT)
    print(f"Auto-detected VisDrone input format: {detected_format}")
    print(f"Auto-detected input root: {detected_root}")

    if detected_format == "yolo":
        validate_visdrone_root(detected_root)
        return detected_root.resolve()

    converted_yolo_root = prepare_clean_dir(args.converted_yolo_root.resolve())

    if detected_format == "raw_zip":
        extracted_raw_root = prepare_clean_dir(KAGGLE_WORKING_ROOT / "visdrone_raw")
        for zip_name in ZIP_NAMES.values():
            zip_path = detected_root / zip_name
            if zip_path.exists():
                print(f"Extracting {zip_path} -> {extracted_raw_root}")
                with zipfile.ZipFile(zip_path, "r") as zip_file:
                    zip_file.extractall(extracted_raw_root)
        raw_root = extracted_raw_root
    else:
        raw_root = detected_root.resolve()

    convert_visdrone_det_split(raw_root / RAW_TRAIN_DIR_NAME, "train", converted_yolo_root)
    convert_visdrone_det_split(raw_root / RAW_VAL_DIR_NAME, "val", converted_yolo_root)

    for test_dir_name in RAW_TEST_DIR_NAMES:
        test_dir = raw_root / test_dir_name
        if test_dir.exists():
            ensure_symlink(test_dir / "images", converted_yolo_root / "images" / "test")
            break

    validate_visdrone_root(converted_yolo_root)
    print(f"Converted raw VisDrone into YOLO format: {converted_yolo_root}")
    return converted_yolo_root


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
    prepare_merged_root(merged_root)

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
    data_root = prepare_yolo_data_root(args)
    validate_nonempty_training_data(data_root, "Prepared YOLO dataset")
    merged_root = build_merged_dataset(data_root, args.merged_root)
    validate_nonempty_training_data(merged_root, "Merged person/vehicle dataset")
    data_yaml = write_dataset_yaml(merged_root, args.output_yaml)

    print(f"Using dataset root: {data_root}")
    print(f"Generated merged dataset: {merged_root}")
    print(f"Generated YAML: {data_yaml}")
    print("Merged dataset root is rebuilt on every run to avoid stale labels and symlinks.")
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
