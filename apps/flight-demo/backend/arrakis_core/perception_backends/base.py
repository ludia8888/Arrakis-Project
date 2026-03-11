from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from schemas import DetectionBox


logger = logging.getLogger("arrakis.perception.base")


@dataclass(frozen=True)
class InferenceResult:
    detections: list[DetectionBox]
    mode: str


class PerceptionBackend(ABC):
    @property
    @abstractmethod
    def mode(self) -> str: ...

    @abstractmethod
    def infer(self, frame: Any, metadata: dict[str, object], degrade_step: int) -> InferenceResult: ...


def resolve_model_path(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.exists():
            logger.info("Resolved model path %s", path)
            return path
    logger.info("No model path resolved from %d candidates", len(candidates))
    return None
