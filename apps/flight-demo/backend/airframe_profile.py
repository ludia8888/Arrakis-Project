"""Airframe profile system for drone parameter management.

Provides a structured, validated configuration model for airframe-specific
flight parameters. Supports VTOL quadplanes and standard quadcopters.
Profiles are loaded from YAML files and threaded through the system via
explicit dependency injection.

Usage:
    # Load by environment variable (ARRAKIS_AIRFRAME_PROFILE)
    profile = load_profile()

    # Load by name (looks in backend/airframes/{name}.yaml)
    profile = load_profile("default-quadcopter")

    # Load by file path
    profile = load_profile("/path/to/custom.yaml")
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

AirframeType = Literal["vtol", "quadcopter"]

logger = logging.getLogger("arrakis.airframe")


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class AltitudeConfig(BaseModel):
    """Altitude parameters in meters AGL."""

    model_config = ConfigDict(frozen=True)

    takeoff_m: float = 40.0
    cruise_m: float = 60.0
    recovery_m: float = 50.0


class GeometryConfig(BaseModel):
    """Spatial geometry for route planning, geofence generation, and mission thresholds."""

    model_config = ConfigDict(frozen=True)

    loiter_radius_m: float = 35.0
    home_bubble_radius_m: float = 80.0
    home_operation_bubble_radius_m: float = 160.0
    outbound_startup_bubble_radius_m: float = 220.0
    geofence_half_width_m: float = 120.0
    waypoint_turn_bubble_radius_m: float = 155.0
    home_arrival_radius_m: float = 120.0


class SafetyConfig(BaseModel):
    """Safety thresholds."""

    model_config = ConfigDict(frozen=True)

    battery_rtl_threshold_percent: float = 20.0
    min_gps_fix_type: int = 3
    min_gps_satellites: int = 6
    gps_degraded_rtl_timeout_seconds: float = 8.0
    min_progress_airspeed_mps: float = 12.0
    min_progress_groundspeed_mps: float = 4.0
    progress_min_delta_m: float = 12.0
    progress_stall_timeout_seconds: float = 12.0
    sensor_inconsistency_altitude_jump_m: float = 8.0
    sensor_inconsistency_airspeed_jump_mps: float = 10.0
    sensor_inconsistency_timeout_seconds: float = 4.0


class RecoveryThresholdsConfig(BaseModel):
    """Thresholds for multicopter recovery phase convergence."""

    model_config = ConfigDict(frozen=True)

    speed_threshold_mps: float
    home_distance_threshold_m: float
    altitude_deviation_m: float
    dwell_seconds: float
    timeout_seconds: float


class RecoveryConfig(BaseModel):
    """Primary and fallback recovery thresholds."""

    model_config = ConfigDict(frozen=True)

    primary: RecoveryThresholdsConfig = RecoveryThresholdsConfig(
        speed_threshold_mps=14.0,
        home_distance_threshold_m=80.0,
        altitude_deviation_m=12.0,
        dwell_seconds=3.0,
        timeout_seconds=25.0,
    )
    fallback: RecoveryThresholdsConfig = RecoveryThresholdsConfig(
        speed_threshold_mps=17.0,
        home_distance_threshold_m=110.0,
        altitude_deviation_m=18.0,
        dwell_seconds=2.0,
        timeout_seconds=18.0,
    )


class TimingConfig(BaseModel):
    """Timeout and timing parameters."""

    model_config = ConfigDict(frozen=True)

    takeoff_timeout_seconds: float = 45.0
    transition_timeout_seconds: float = 25.0
    landing_timeout_seconds: float = 90.0
    vtol_landing_approach_min_m: float = 140.0


class SpeedConfig(BaseModel):
    """Speed parameters for simulation fidelity (MockAdapter) and reference."""

    model_config = ConfigDict(frozen=True)

    cruise_airspeed_mps: float = 22.0
    cruise_groundspeed_mps: float = 20.0
    takeoff_airspeed_mps: float = 4.0
    takeoff_groundspeed_mps: float = 4.0
    transition_fw_airspeed_mps: float = 18.0
    transition_fw_groundspeed_mps: float = 16.0
    transition_mc_airspeed_mps: float = 9.0
    transition_mc_groundspeed_mps: float = 8.0
    rtl_min_airspeed_mps: float = 16.0
    rtl_min_groundspeed_mps: float = 14.0
    landing_descent_mps: float = 6.0
    landing_airspeed_mps: float = 4.0
    landing_groundspeed_mps: float = 3.0
    recovery_decel_airspeed_mps2: float = 2.8
    recovery_decel_groundspeed_mps2: float = 2.2
    recovery_min_airspeed_mps: float = 10.0
    recovery_min_groundspeed_mps: float = 8.0
    recovery_movement_speed_mps: float = 6.0
    rtl_movement_speed_mps: float = 12.0
    rtl_arrival_airspeed_mps: float = 12.0
    rtl_arrival_groundspeed_mps: float = 10.0
    rtl_arrival_distance_m: float = 20.0
    mission_movement_speed_mps: float = 16.0
    battery_drain_rate: float = 0.02


# ---------------------------------------------------------------------------
# Top-level profile
# ---------------------------------------------------------------------------


class AirframeProfile(BaseModel):
    """Complete airframe profile. Frozen after construction for safety."""

    model_config = ConfigDict(frozen=True)

    name: str = "default-vtol"
    description: str = "Default VTOL quadplane profile"
    airframe_type: AirframeType = "vtol"
    altitudes: AltitudeConfig = AltitudeConfig()
    geometry: GeometryConfig = GeometryConfig()
    safety: SafetyConfig = SafetyConfig()
    recovery: RecoveryConfig = RecoveryConfig()
    timing: TimingConfig = TimingConfig()
    speeds: SpeedConfig = SpeedConfig()

    @property
    def is_vtol(self) -> bool:
        """True for VTOL quadplanes that require FW/MC transitions."""
        return self.airframe_type == "vtol"

    @model_validator(mode="after")
    def validate_physical_consistency(self) -> AirframeProfile:
        errors: list[str] = []

        if self.airframe_type == "vtol":
            # VTOL: recovery altitude must be between takeoff and cruise
            if not (self.altitudes.takeoff_m <= self.altitudes.recovery_m <= self.altitudes.cruise_m):
                errors.append(
                    f"altitude ordering violated: takeoff({self.altitudes.takeoff_m}m) "
                    f"<= recovery({self.altitudes.recovery_m}m) "
                    f"<= cruise({self.altitudes.cruise_m}m)"
                )

            # VTOL: primary recovery thresholds should be tighter than fallback
            if self.recovery.primary.speed_threshold_mps > self.recovery.fallback.speed_threshold_mps:
                errors.append(
                    f"primary recovery speed_threshold({self.recovery.primary.speed_threshold_mps}mps) "
                    f"should be <= fallback({self.recovery.fallback.speed_threshold_mps}mps)"
                )
        else:
            # Quadcopter: just validate takeoff <= cruise (no recovery phase)
            if self.altitudes.takeoff_m > self.altitudes.cruise_m:
                errors.append(
                    f"takeoff altitude ({self.altitudes.takeoff_m}m) "
                    f"must be <= cruise altitude ({self.altitudes.cruise_m}m)"
                )

        # Common validations (all airframe types)

        # Home bubble must fit inside home operation bubble
        if self.geometry.home_bubble_radius_m > self.geometry.home_operation_bubble_radius_m:
            errors.append(
                f"home_bubble_radius({self.geometry.home_bubble_radius_m}m) "
                f"must be <= home_operation_bubble_radius({self.geometry.home_operation_bubble_radius_m}m)"
            )

        # Home operation bubble must fit inside outbound startup bubble
        if self.geometry.home_operation_bubble_radius_m > self.geometry.outbound_startup_bubble_radius_m:
            errors.append(
                f"home_operation_bubble_radius({self.geometry.home_operation_bubble_radius_m}m) "
                f"must be <= outbound_startup_bubble_radius({self.geometry.outbound_startup_bubble_radius_m}m)"
            )

        # Geofence corridor must be at least as wide as the loiter radius
        if self.geometry.geofence_half_width_m < self.geometry.loiter_radius_m:
            errors.append(
                f"geofence_half_width({self.geometry.geofence_half_width_m}m) "
                f"must be >= loiter_radius({self.geometry.loiter_radius_m}m)"
            )

        # Battery threshold sanity range
        if not (5.0 <= self.safety.battery_rtl_threshold_percent <= 50.0):
            errors.append(
                f"battery_rtl_threshold({self.safety.battery_rtl_threshold_percent}%) "
                f"must be between 5% and 50%"
            )
        if self.safety.min_gps_fix_type < 1:
            errors.append(
                f"min_gps_fix_type({self.safety.min_gps_fix_type}) must be >= 1"
            )
        if self.safety.min_gps_satellites < 0:
            errors.append(
                f"min_gps_satellites({self.safety.min_gps_satellites}) must be >= 0"
            )
        if self.safety.gps_degraded_rtl_timeout_seconds <= 0:
            errors.append(
                "gps_degraded_rtl_timeout_seconds must be > 0"
            )
        if self.safety.min_progress_airspeed_mps <= 0 or self.safety.min_progress_groundspeed_mps < 0:
            errors.append(
                "progress speed thresholds must be positive"
            )
        if self.safety.progress_min_delta_m <= 0 or self.safety.progress_stall_timeout_seconds <= 0:
            errors.append(
                "progress stall thresholds must be > 0"
            )
        if (
            self.safety.sensor_inconsistency_altitude_jump_m <= 0
            or self.safety.sensor_inconsistency_airspeed_jump_mps <= 0
            or self.safety.sensor_inconsistency_timeout_seconds <= 0
        ):
            errors.append(
                "sensor inconsistency thresholds must be > 0"
            )

        if errors:
            raise ValueError(
                f"Airframe profile '{self.name}' has physical consistency errors:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )
        return self


# ---------------------------------------------------------------------------
# Profile loader
# ---------------------------------------------------------------------------

_PROFILES_DIR = Path(__file__).parent / "airframes"


def load_profile(name_or_path: str | None = None) -> AirframeProfile:
    """Load an airframe profile by name or file path.

    Resolution order:
    1. If *name_or_path* is ``None``, check ``ARRAKIS_AIRFRAME_PROFILE`` env var.
    2. If still ``None``, return the built-in default profile.
    3. If the value contains a path separator or ends with ``.yaml``/``.yml``,
       treat it as a file path and load directly.
    4. Otherwise look for ``{name}.yaml`` in the built-in ``airframes/`` directory.
    """
    selector = name_or_path or os.getenv("ARRAKIS_AIRFRAME_PROFILE")

    if selector is None:
        logger.info("No airframe profile specified, using built-in default")
        return AirframeProfile()

    path = Path(selector)
    if not path.suffix:
        path = _PROFILES_DIR / f"{selector}.yaml"

    if not path.exists():
        available = sorted(p.stem for p in _PROFILES_DIR.glob("*.yaml"))
        raise FileNotFoundError(
            f"Airframe profile not found: {path}\n"
            f"Available built-in profiles: {', '.join(available) or '(none)'}"
        )

    logger.info("Loading airframe profile from %s", path)
    with open(path) as f:
        data = yaml.safe_load(f)

    profile = AirframeProfile.model_validate(data)
    logger.info("Loaded airframe profile: %s — %s", profile.name, profile.description)
    return profile
