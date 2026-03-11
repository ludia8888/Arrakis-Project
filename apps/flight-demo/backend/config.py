from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_CANDIDATES = [
    REPO_ROOT / "best.pt",
    REPO_ROOT / "runs" / "visdrone" / "yolo26s-person-vehicle-p100" / "weights" / "best.pt",
    REPO_ROOT / "yolo26s.pt",
]


@dataclass(frozen=True)
class VideoConfig:
    width: int = 1280
    height: int = 720
    fps: int = 12
    jpeg_quality: int = 75
    fallback_width: int = 960


@dataclass(frozen=True)
class RecoveryThresholds:
    speed_threshold_mps: float
    home_distance_threshold_m: float
    altitude_deviation_m: float
    dwell_seconds: float
    timeout_seconds: float


PRIMARY_RECOVERY = RecoveryThresholds(
    speed_threshold_mps=14.0,
    home_distance_threshold_m=80.0,
    altitude_deviation_m=12.0,
    dwell_seconds=3.0,
    timeout_seconds=25.0,
)

FALLBACK_RECOVERY = RecoveryThresholds(
    speed_threshold_mps=17.0,
    home_distance_threshold_m=110.0,
    altitude_deviation_m=18.0,
    dwell_seconds=2.0,
    timeout_seconds=18.0,
)

TAKEOFF_ALT_M = 40.0
CRUISE_ALT_M = 60.0
RECOVERY_ALT_M = 50.0
LOITER_RADIUS_M = 35.0
HOME_BUBBLE_RADIUS_M = 80.0
GEOFENCE_HALF_WIDTH_M = 120.0
BATTERY_RTL_THRESHOLD = 20.0
WEBSOCKET_HZ = 5
