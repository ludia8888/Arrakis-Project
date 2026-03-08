# Arrakis YOLO Workflow

This repository has two jobs:

1. Fine-tune `yolo26s.pt` on VisDrone for a strict `person / vehicle` detector.
2. Run the trained checkpoint locally through a browser overlay or OpenCV preview.

## Repository layout

- `kaggle_train_visdrone_yolo26s.py`: Kaggle training entrypoint for VisDrone.
- `yolo_frontend_app.py`: local FastAPI app for browser-based overlay testing.
- `realtime_yolo26s.py`: local OpenCV preview for webcam or screen capture.
- `model_runtime.py`: shared model and device resolution for local inference.
- `yolo26s.pt`: base checkpoint.

## Environment

Python `3.12` is the current target.

Create and install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

This also installs the `kaggle` CLI used for notebook, dataset, and output operations.

## Local model selection

Local inference now uses the following resolution order:

1. `ARRAKIS_MODEL_PATH`
2. `./best.pt`
3. `./yolo26s.pt`

This means the simplest handoff from Kaggle is:

1. Download `best.pt` from Kaggle.
2. Place it in the repository root as `best.pt`.
3. Start the local frontend or realtime runner.

If you keep the checkpoint elsewhere, set:

```bash
export ARRAKIS_MODEL_PATH=/absolute/path/to/best.pt
```

## Run the browser frontend

```bash
source .venv/bin/activate
./run_yolo_frontend.sh
```

Then open `http://127.0.0.1:8000`.

`/health` also reports the currently loaded model and device.

## Run the OpenCV preview

Default model resolution is shared with the frontend:

```bash
source .venv/bin/activate
./run_realtime_yolo26s.sh --source webcam
```

Screen capture example:

```bash
./run_realtime_yolo26s.sh --source screen --select-region --view split
```

## Kaggle training flow

The training script expects a YOLO-style VisDrone root:

```text
VisDrone/
  images/
    train/
    val/
  labels/
    train/
    val/
```

The script:

- keeps a strict split: `train=train`, `val=val`
- remaps VisDrone classes into:
  - `0: person`
  - `1: vehicle`
- rebuilds the generated merged dataset on every run to avoid stale labels
- supports `--resume-from` and `--save-period`
- auto-detects Kaggle `/kaggle/input` when `--data-root` is omitted
- converts raw VisDrone Kaggle inputs to YOLO format automatically when needed

Example:

```bash
python kaggle_train_visdrone_yolo26s.py \
  --data-root /kaggle/input/visdrone-yolo/VisDrone \
  --weights /kaggle/working/Arrakis-Project/yolo26s.pt \
  --epochs 50 \
  --imgsz 1280 \
  --batch 4 \
  --workers 4 \
  --device 0 \
  --cache \
  --save-period 1 \
  --name yolo26s-person-vehicle-p100
```

Expected outputs:

```text
/kaggle/working/runs/visdrone/<run-name>/weights/best.pt
/kaggle/working/runs/visdrone/<run-name>/weights/last.pt
```

### Kaggle GitHub notebook mode

If the Kaggle notebook is linked directly to this repository and points at
[`kaggle_train_visdrone_yolo26s.py`](/Users/isihyeon/Desktop/Arrakis-Project/kaggle_train_visdrone_yolo26s.py),
you do not need to paste notebook cells.

Attach a VisDrone dataset to the notebook input and run the notebook. The script will:

1. Detect whether the input is YOLO format, raw directories, or raw zip files
2. Convert raw VisDrone data into YOLO labels if needed
3. Build the strict `person / vehicle` dataset
4. Start training with the repository defaults

Outside Kaggle, keep using `--data-root`.

If you prefer a GitHub-backed Kaggle notebook instead of a `.py` entrypoint, use
[`kaggle_train_visdrone_yolo26s.ipynb`](/Users/isihyeon/Desktop/Arrakis-Project/kaggle_train_visdrone_yolo26s.ipynb).
That notebook clones the repo, installs requirements, runs the training script, and copies `best.pt` / `last.pt`
into `/kaggle/working`.
For Kaggle P100 runs, the notebook installs `ultralytics` with `--no-deps` so it does not replace the platform's
preinstalled CUDA/PyTorch stack.

## Kaggle CLI setup

The local `.venv` includes the official `kaggle` CLI.

Verify:

```bash
source .venv/bin/activate
kaggle --version
```

Authentication options:

1. Put `kaggle.json` in `~/.kaggle/kaggle.json` and set `chmod 600 ~/.kaggle/kaggle.json`
2. Or export `KAGGLE_USERNAME` and `KAGGLE_KEY`

After authentication, this Codex environment can run Kaggle CLI commands directly.

## Operational notes

- `best.pt`, `last.pt`, `epoch*.pt`, and `runs/` are git-ignored so local experiments do not pollute the repo.
- The local frontend is for qualitative testing, not high-throughput serving. It still uses browser capture and HTTP requests per frame.
