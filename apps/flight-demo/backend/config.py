from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
LOG_LEVEL = os.getenv("ARRAKIS_LOG_LEVEL", "INFO").upper()
ENV_MODEL_PATH = os.getenv("ARRAKIS_DETECTOR_MODEL_PATH")
STATE_DUMP_PATH = os.getenv("ARRAKIS_STATE_DUMP_PATH")
ARDUPILOT_CONNECTION = os.getenv("ARRAKIS_ARDUPILOT_CONNECTION", "udp:127.0.0.1:14550")
ARDUPILOT_VIDEO_SOURCE = os.getenv("ARRAKIS_ARDUPILOT_VIDEO_SOURCE")
ARDUPILOT_HEARTBEAT_TIMEOUT = float(os.getenv("ARRAKIS_ARDUPILOT_HEARTBEAT_TIMEOUT", "30"))
ARDUPILOT_COMMAND_TIMEOUT = float(os.getenv("ARRAKIS_ARDUPILOT_COMMAND_TIMEOUT", "10"))
ARDUPILOT_TELEMETRY_HZ = float(os.getenv("ARRAKIS_ARDUPILOT_TELEMETRY_HZ", "5"))
ARDUPILOT_DEFAULT_HOME_LAT = float(os.getenv("ARRAKIS_ARDUPILOT_DEFAULT_HOME_LAT", "37.5665"))
ARDUPILOT_DEFAULT_HOME_LON = float(os.getenv("ARRAKIS_ARDUPILOT_DEFAULT_HOME_LON", "126.9780"))
ARDUPILOT_MODE_QLOITER = os.getenv("ARRAKIS_ARDUPILOT_MODE_QLOITER", "QLOITER")
ARDUPILOT_MODE_GUIDED = os.getenv("ARRAKIS_ARDUPILOT_MODE_GUIDED", "GUIDED")
ARDUPILOT_MODE_AUTO = os.getenv("ARRAKIS_ARDUPILOT_MODE_AUTO", "AUTO")
ARDUPILOT_MODE_LOITER = os.getenv("ARRAKIS_ARDUPILOT_MODE_LOITER", "LOITER")
ARDUPILOT_MODE_RTL = os.getenv("ARRAKIS_ARDUPILOT_MODE_RTL", "RTL")
ARDUPILOT_MODE_QLAND = os.getenv("ARRAKIS_ARDUPILOT_MODE_QLAND", "QLAND")
DEFAULT_MODEL_CANDIDATES = (
    ([Path(ENV_MODEL_PATH).expanduser()] if ENV_MODEL_PATH else [])
    + [
        REPO_ROOT / "best.pt",
        REPO_ROOT / "runs" / "visdrone" / "yolo26s-person-vehicle-p100" / "weights" / "best.pt",
        REPO_ROOT / "yolo26s.pt",
    ]
)


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
HOME_OPERATION_BUBBLE_RADIUS_M = 160.0
OUTBOUND_STARTUP_BUBBLE_RADIUS_M = 220.0
GEOFENCE_HALF_WIDTH_M = 120.0
WAYPOINT_TURN_BUBBLE_RADIUS_M = 155.0
BATTERY_RTL_THRESHOLD = 20.0
WEBSOCKET_HZ = 5
