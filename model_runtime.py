from __future__ import annotations

import os
from pathlib import Path

import torch


BASE_DIR = Path(__file__).resolve().parent
MODEL_ENV_VAR = "ARRAKIS_MODEL_PATH"
DEFAULT_MODEL_NAMES = ("best.pt", "yolo26s.pt")


def _normalize_model_path(path_value: str | Path) -> Path:
    candidate = Path(path_value).expanduser()
    if candidate.is_absolute():
        return candidate
    return BASE_DIR / candidate


def resolve_model_path(explicit_path: str | Path | None = None) -> Path:
    candidates: list[Path] = []

    if explicit_path:
        candidates.append(_normalize_model_path(explicit_path))

    env_model_path = os.getenv(MODEL_ENV_VAR)
    if env_model_path:
        candidates.append(_normalize_model_path(env_model_path))

    candidates.extend(BASE_DIR / model_name for model_name in DEFAULT_MODEL_NAMES)

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    searched = "\n".join(str(candidate.resolve(strict=False)) for candidate in candidates)
    raise FileNotFoundError(
        "Could not find a model checkpoint. Looked for:\n"
        f"{searched}\n"
        f"Set {MODEL_ENV_VAR} or place best.pt in the repository root."
    )


def resolve_device() -> str:
    if torch.cuda.is_available():
        return "cuda:0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
