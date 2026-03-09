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


def count_nonempty_label_files(labels_dir: Path) -> int:
    return sum(1 for path in labels_dir.glob("*.txt") if path.stat().st_size > 0)


def collect_split_counts(data_root: Path) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for split in ("train", "val"):
        images_dir = data_root / "images" / split
        labels_dir = data_root / "labels" / split
        counts[split] = {
            "images": count_image_files(images_dir),
            "labels": len(list(labels_dir.glob("*.txt"))),
            "nonempty_labels": count_nonempty_label_files(labels_dir),
        }
    return counts


def print_split_counts(title: str, counts: dict[str, dict[str, int]]) -> None:
    print(title)
    for split, split_counts in counts.items():
        print(f"  {split}: images={split_counts['images']}, labels={split_counts['labels']}, nonempty_labels={split_counts['nonempty_labels']}")


def validate_nonempty_training_data(data_root: Path, dataset_name: str) -> dict[str, dict[str, int]]:
    counts = collect_split_counts(data_root)
    print_split_counts(f"{dataset_name} counts:", counts)

    missing_images = [split for split, split_counts in counts.items() if split_counts["images"] == 0]
    missing_labels = [split for split, split_counts in counts.items() if split_counts["labels"] == 0]
    empty_labels = [split for split, split_counts in counts.items() if split_counts["labels"] > 0 and split_counts["nonempty_labels"] == 0]

    if missing_images or missing_labels or empty_labels:
        problems: list[str] = []
        if missing_images:
            problems.append(f"no images in splits: {', '.join(missing_images)}")
        if missing_labels:
            problems.append(f"no label txt files in splits: {', '.join(missing_labels)}")
        if empty_labels:
            problems.append(f"all label files are empty (no annotations) in splits: {', '.join(empty_labels)}")
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


def link_or_copy_images(source_dir: Path, dest_dir: Path) -> int:
    """Create hardlinks (or copies) of images, avoiding symlinks that confuse YOLO label derivation."""
    source_dir = source_dir.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for img_file in sorted(source_dir.iterdir()):
        if img_file.is_file() and img_file.suffix.lower() in IMAGE_SUFFIXES:
            dest_file = dest_dir / img_file.name
            if dest_file.exists():
                continue
            try:
                os.link(img_file, dest_file)
            except OSError:
                shutil.copy2(img_file, dest_file)
            count += 1
    return count


def delete_yolo_cache_files(root: Path) -> None:
    """Remove .cache files that may contain stale label mappings."""
    for cache_file in root.rglob("*.cache"):
        try:
            cache_file.unlink()
            print(f"Deleted cache file: {cache_file}")
        except OSError:
            pass


def verify_label_mapping(data_root: Path, split: str = "train", sample_size: int = 5) -> None:
    """Verify YOLO can derive label paths from image paths (mirrors Ultralytics img2label_paths)."""
    images_dir = data_root / "images" / split
    sa = f"{os.sep}images{os.sep}"
    sb = f"{os.sep}labels{os.sep}"

    image_files = sorted(
        p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )[:sample_size]

    print(f"Label mapping verification ({split}, {len(image_files)} samples):")
    for img in image_files:
        img_str = str(img)
        label_str = sb.join(img_str.rsplit(sa, 1)).rsplit(".", 1)[0] + ".txt"
        label_exists = Path(label_str).exists()
        label_lines = 0
        if label_exists:
            label_lines = len(Path(label_str).read_text().strip().splitlines())
        resolved_str = str(img.resolve())
        is_resolved_same = resolved_str == img_str
        print(f"  {img.name}: label_exists={label_exists}, lines={label_lines}, "
              f"path_resolved_same={is_resolved_same}")
        if not is_resolved_same:
            resolved_label = sb.join(resolved_str.rsplit(sa, 1)).rsplit(".", 1)[0] + ".txt"
            print(f"    WARN resolved image: {resolved_str}")
            print(f"    WARN resolved label: {resolved_label} (exists={Path(resolved_label).exists()})")


def prepare_merged_root(merged_root: Path) -> None:
    merged_root.mkdir(parents=True, exist_ok=True)
    remove_path(merged_root / "images")
    remove_path(merged_root / "labels")


def _has_label_files(labels_dir: Path) -> bool:
    return labels_dir.is_dir() and any(labels_dir.glob("*.txt"))


def classify_visdrone_root(root: Path) -> str | None:
    images_train = root / "images" / "train"
    labels_train = root / "labels" / "train"
    if images_train.exists() and labels_train.exists() and _has_label_files(labels_train):
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


def _unwrap_nested_dir(source_dir: Path) -> Path:
    """Handle double-nested dirs like VisDrone2019-DET-train/VisDrone2019-DET-train/."""
    if (source_dir / "images").is_dir() and (source_dir / "annotations").is_dir():
        return source_dir
    nested = source_dir / source_dir.name
    if nested.is_dir() and (nested / "images").is_dir() and (nested / "annotations").is_dir():
        print(f"Unwrapping nested directory: {nested}")
        return nested
    return source_dir


def convert_visdrone_det_split(source_dir: Path, split_name: str, out_root: Path) -> None:
    source_dir = _unwrap_nested_dir(source_dir)
    source_images = source_dir / "images"
    if not source_images.is_dir():
        existing = [p.name for p in source_dir.iterdir()] if source_dir.is_dir() else []
        raise FileNotFoundError(
            f"VisDrone images directory not found: {source_images}\n"
            f"Contents of {source_dir}: {existing}"
        )
    annotations_dir = source_dir / "annotations"
    if not annotations_dir.is_dir():
        existing = [p.name for p in source_dir.iterdir()]
        raise FileNotFoundError(
            f"VisDrone annotations directory not found: {annotations_dir}\n"
            f"Contents of {source_dir}: {existing}\n"
            "This dataset may not include raw annotations. "
            "Use a dataset with VisDrone-DET annotation files, or supply pre-converted YOLO labels via --data-root."
        )
    images_link = out_root / "images" / split_name
    labels_dir = out_root / "labels" / split_name
    ensure_symlink(source_images, images_link)
    labels_dir.mkdir(parents=True, exist_ok=True)

    for ann_file in sorted(annotations_dir.glob("*.txt")):
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

            x, y, w, h = (int(float(v)) for v in row[:4])
            class_id = int(float(row[5])) - 1
            if class_id < 0 or class_id > 9:
                continue

            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(image_width, x + w)
            y2 = min(image_height, y + h)
            if x2 <= x1 or y2 <= y1:
                continue
            w_clamped = x2 - x1
            h_clamped = y2 - y1
            x_center = (x1 + w_clamped / 2) * dw
            y_center = (y1 + h_clamped / 2) * dh
            w_norm = w_clamped * dw
            h_norm = h_clamped * dh
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
        for split_key in ("train", "val", "test"):
            zip_path = detected_root / ZIP_NAMES[split_key]
            if zip_path.exists():
                print(f"Extracting {zip_path} -> {extracted_raw_root}")
                with zipfile.ZipFile(zip_path, "r") as zip_file:
                    zip_file.extractall(extracted_raw_root, filter="data")
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
        src_images = data_root / "images" / split
        n = link_or_copy_images(src_images, merged_root / "images" / split)
        print(f"Linked/copied {n} images for {split} split")

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

    # Verify YOLO can derive label paths from image paths
    verify_label_mapping(merged_root, "train")
    verify_label_mapping(merged_root, "val")

    # Remove stale cache files that may contain wrong label mappings
    delete_yolo_cache_files(merged_root)
    if running_on_kaggle():
        delete_yolo_cache_files(KAGGLE_INPUT_ROOT)

    print(f"Using dataset root: {data_root}")
    print(f"Generated merged dataset: {merged_root}")
    print(f"Generated YAML: {data_yaml}")
    print("Images are hardlinked/copied (not symlinked) to avoid YOLO label path resolution issues.")
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
        model.train(resume=True)
    else:
        model = YOLO(args.weights)
        model.train(pretrained=True, **train_kwargs)

    trainer = getattr(model, "trainer", None)
    if trainer is None:
        print("Warning: model.trainer is not available; cannot determine output paths.")
    else:
        save_dir = Path(trainer.save_dir)
        best_path = save_dir / "weights" / "best.pt"
        last_path = save_dir / "weights" / "last.pt"
        print(f"Run directory: {save_dir}")
        print(f"Best weights: {best_path}")
        print(f"Last weights: {last_path}")


if __name__ == "__main__":
    main()
