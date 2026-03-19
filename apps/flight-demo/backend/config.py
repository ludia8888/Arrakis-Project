from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


REPO_ROOT = Path(__file__).resolve().parents[3]
LOG_LEVEL = os.getenv("ARRAKIS_LOG_LEVEL", "INFO").upper()
ENV_MODEL_PATH = os.getenv("ARRAKIS_DETECTOR_MODEL_PATH")
STATE_DUMP_PATH = os.getenv("ARRAKIS_STATE_DUMP_PATH")
EVENT_LOG_PATH = os.getenv(
    "ARRAKIS_EVENT_LOG_PATH",
    str(REPO_ROOT / "runtime_logs" / "arrakis"),
)
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
ARDUPILOT_MODE_LAND = os.getenv("ARRAKIS_ARDUPILOT_MODE_LAND", "LAND")
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


WEBSOCKET_HZ = 5

LinkProfileName = Literal["sitl", "sik"]


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw is not None else default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw is not None else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class LinkProfileConfig:
    name: LinkProfileName
    telemetry_degraded_after_s: float
    telemetry_lost_after_s: float
    telemetry_stale_debounce: int
    position_loss_rtl_timeout_s: float
    gps_degraded_rtl_timeout_s: float
    control_plane_revalidate_s: float
    gcs_heartbeat_enabled: bool
    gcs_heartbeat_period_s: float
    mission_upload_retries: int


def _default_link_profile(name: LinkProfileName) -> LinkProfileConfig:
    if name == "sik":
        return LinkProfileConfig(
            name="sik",
            telemetry_degraded_after_s=3.0,
            telemetry_lost_after_s=8.0,
            telemetry_stale_debounce=2,
            position_loss_rtl_timeout_s=6.0,
            gps_degraded_rtl_timeout_s=8.0,
            control_plane_revalidate_s=5.0,
            gcs_heartbeat_enabled=True,
            gcs_heartbeat_period_s=1.0,
            mission_upload_retries=3,
        )
    return LinkProfileConfig(
        name="sitl",
        telemetry_degraded_after_s=0.8,
        telemetry_lost_after_s=2.5,
        telemetry_stale_debounce=1,
        position_loss_rtl_timeout_s=6.0,
        gps_degraded_rtl_timeout_s=8.0,
        control_plane_revalidate_s=5.0,
        gcs_heartbeat_enabled=True,
        gcs_heartbeat_period_s=1.0,
        mission_upload_retries=3,
    )


def resolve_link_profile_config() -> LinkProfileConfig:
    raw_name = os.getenv("ARRAKIS_LINK_PROFILE", "sitl").strip().lower()
    profile_name: LinkProfileName = "sik" if raw_name == "sik" else "sitl"
    default = _default_link_profile(profile_name)
    return LinkProfileConfig(
        name=profile_name,
        telemetry_degraded_after_s=_env_float(
            "ARRAKIS_TELEMETRY_DEGRADED_AFTER_S",
            default.telemetry_degraded_after_s,
        ),
        telemetry_lost_after_s=_env_float(
            "ARRAKIS_TELEMETRY_LOST_AFTER_S",
            default.telemetry_lost_after_s,
        ),
        telemetry_stale_debounce=max(
            1,
            _env_int("ARRAKIS_TELEMETRY_STALE_DEBOUNCE", default.telemetry_stale_debounce),
        ),
        position_loss_rtl_timeout_s=_env_float(
            "ARRAKIS_POSITION_LOSS_RTL_TIMEOUT_S",
            default.position_loss_rtl_timeout_s,
        ),
        gps_degraded_rtl_timeout_s=_env_float(
            "ARRAKIS_GPS_DEGRADED_RTL_TIMEOUT_S",
            default.gps_degraded_rtl_timeout_s,
        ),
        control_plane_revalidate_s=_env_float(
            "ARRAKIS_CONTROL_PLANE_REVALIDATE_S",
            default.control_plane_revalidate_s,
        ),
        gcs_heartbeat_enabled=_env_bool(
            "ARRAKIS_GCS_HEARTBEAT_ENABLED",
            default.gcs_heartbeat_enabled,
        ),
        gcs_heartbeat_period_s=max(
            0.1,
            _env_float("ARRAKIS_GCS_HEARTBEAT_PERIOD_S", default.gcs_heartbeat_period_s),
        ),
        mission_upload_retries=max(
            1,
            _env_int("ARRAKIS_MISSION_UPLOAD_RETRIES", default.mission_upload_retries),
        ),
    )


ARRAKIS_LINK_PROFILE = resolve_link_profile_config()
