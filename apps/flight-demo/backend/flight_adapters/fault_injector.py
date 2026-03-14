"""Fault injection framework for MockAdapter realistic simulation.

All faults are disabled by default. Callers opt in via FaultProfile or
individual configuration dataclasses. This ensures backward compatibility
with existing tests that use the default MockAdapter.

Usage:
    # Default — no faults (identical to current MockAdapter behavior)
    adapter = MockAdapter(profile)

    # Realistic outdoor conditions
    adapter = MockAdapter(profile, fault_profile=FaultProfile.realistic())

    # Extreme stress testing
    adapter = MockAdapter(profile, fault_profile=FaultProfile.stress())

    # Custom
    adapter = MockAdapter(profile, fault_profile=FaultProfile(
        gps=GPSNoiseConfig(enabled=True, horizontal_stddev_m=2.0),
    ))
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GPSNoiseConfig:
    """Gaussian noise on position in meters, plus random dropout events."""

    enabled: bool = False
    horizontal_stddev_m: float = 1.5  # typical GPS accuracy (~1-3m CEP)
    vertical_stddev_m: float = 3.0  # GPS vertical accuracy is worse
    dropout_probability: float = 0.0  # per-tick chance of returning invalid position
    dropout_duration_s: float = 2.0  # how long a single dropout event lasts


@dataclass
class SensorNoiseConfig:
    """Additive noise on barometric altitude and pitot-tube airspeed."""

    enabled: bool = False
    altitude_stddev_m: float = 0.5
    airspeed_stddev_mps: float = 0.3


@dataclass
class WindConfig:
    """Constant base wind plus stochastic gust model."""

    enabled: bool = False
    base_speed_mps: float = 3.0
    base_heading_deg: float = 270.0  # westerly wind
    gust_speed_mps: float = 5.0  # max additional gust magnitude
    gust_probability: float = 0.05  # per-tick chance of a new gust event
    gust_duration_range_s: tuple[float, float] = (1.0, 5.0)


@dataclass
class CommConfig:
    """Communication delay and packet loss simulation."""

    enabled: bool = False
    base_delay_s: float = 0.05  # constant latency per command
    jitter_s: float = 0.02  # standard deviation of latency jitter
    loss_probability: float = 0.0  # per-command chance of complete drop
    loss_duration_s: float = 0.0  # sustained comm-loss window (0 = single drop)


@dataclass
class BatteryConfig:
    """Three-zone non-linear discharge curve.

    Real LiPo batteries drain slowly above 50%, faster between 50-20%,
    and very rapidly below 20% (voltage sag under load).
    """

    enabled: bool = False
    high_drain_rate: float = 0.015  # per second per mps above 50%
    mid_drain_rate: float = 0.025  # per second per mps between 50-20%
    low_drain_rate: float = 0.04  # per second per mps below 20%
    voltage_sag_factor: float = 0.1  # additional drain during high-g maneuvers


@dataclass
class TakeoffDynamicsConfig:
    """Realistic takeoff climb dynamics instead of instantaneous altitude jump."""

    enabled: bool = False
    initial_climb_rate_mps: float = 2.0
    max_climb_rate_mps: float = 5.0
    acceleration_mps2: float = 1.0  # how fast climb rate ramps up


# ---------------------------------------------------------------------------
# FaultProfile — composite configuration
# ---------------------------------------------------------------------------


@dataclass
class FaultProfile:
    """Complete fault injection configuration.

    All sub-configs default to disabled, preserving backward compatibility.
    Use the class methods for pre-baked scenarios.
    """

    gps: GPSNoiseConfig = field(default_factory=GPSNoiseConfig)
    sensors: SensorNoiseConfig = field(default_factory=SensorNoiseConfig)
    wind: WindConfig = field(default_factory=WindConfig)
    comm: CommConfig = field(default_factory=CommConfig)
    battery: BatteryConfig = field(default_factory=BatteryConfig)
    takeoff: TakeoffDynamicsConfig = field(default_factory=TakeoffDynamicsConfig)

    @classmethod
    def realistic(cls) -> FaultProfile:
        """Mild outdoor conditions — typical GPS noise, light wind, rare dropouts."""
        return cls(
            gps=GPSNoiseConfig(enabled=True, horizontal_stddev_m=1.5, dropout_probability=0.01),
            sensors=SensorNoiseConfig(enabled=True),
            wind=WindConfig(enabled=True, base_speed_mps=4.0),
            comm=CommConfig(enabled=True, base_delay_s=0.05, loss_probability=0.02),
            battery=BatteryConfig(enabled=True),
            takeoff=TakeoffDynamicsConfig(enabled=True),
        )

    @classmethod
    def stress(cls) -> FaultProfile:
        """Worst-case conditions for stress testing."""
        return cls(
            gps=GPSNoiseConfig(
                enabled=True,
                horizontal_stddev_m=4.0,
                dropout_probability=0.1,
                dropout_duration_s=5.0,
            ),
            sensors=SensorNoiseConfig(enabled=True, altitude_stddev_m=2.0, airspeed_stddev_mps=1.0),
            wind=WindConfig(enabled=True, base_speed_mps=8.0, gust_speed_mps=12.0, gust_probability=0.15),
            comm=CommConfig(enabled=True, base_delay_s=0.1, jitter_s=0.05, loss_probability=0.1),
            battery=BatteryConfig(enabled=True, voltage_sag_factor=0.3),
            takeoff=TakeoffDynamicsConfig(enabled=True, initial_climb_rate_mps=1.0),
        )

    @classmethod
    def comm_loss_only(cls) -> FaultProfile:
        """Communication problems only — for testing comm resilience."""
        return cls(
            comm=CommConfig(enabled=True, base_delay_s=0.1, jitter_s=0.05, loss_probability=0.15, loss_duration_s=3.0),
        )

    @classmethod
    def gps_denial(cls) -> FaultProfile:
        """Sustained GPS dropout — for testing GPS loss recovery."""
        return cls(
            gps=GPSNoiseConfig(enabled=True, horizontal_stddev_m=6.0, dropout_probability=0.3, dropout_duration_s=8.0),
        )


# ---------------------------------------------------------------------------
# FaultInjector — runtime engine
# ---------------------------------------------------------------------------


class FaultInjector:
    """Runtime fault injection engine.

    Tracks active faults, manages transient events (GPS dropout windows,
    comm loss windows, gusts), and applies perturbations to simulation state.
    Deterministic by default (seed=42) for reproducible test runs.
    """

    def __init__(self, profile: FaultProfile | None = None) -> None:
        self._profile = profile or FaultProfile()
        self._rng = random.Random(42)

        # GPS dropout state
        self._gps_dropout_until: float = 0.0

        # Comm loss state
        self._comm_loss_until: float = 0.0

        # Wind gust state
        self._active_gust: tuple[float, float] | None = None  # (speed, heading_rad)
        self._gust_until: float = 0.0

        # Takeoff state
        self._takeoff_started_at: float | None = None
        self._takeoff_climb_rate: float = 0.0

    def seed(self, seed: int) -> None:
        """Set RNG seed for reproducible test runs."""
        self._rng = random.Random(seed)

    @property
    def profile(self) -> FaultProfile:
        return self._profile

    # -- GPS noise ----------------------------------------------------------

    def apply_gps_noise(
        self, lat: float, lon: float, alt_m: float
    ) -> tuple[float, float, float, bool]:
        """Apply GPS noise and dropout.

        Returns (noisy_lat, noisy_lon, noisy_alt, is_valid).
        When is_valid is False, the position should be treated as unavailable.
        """
        cfg = self._profile.gps
        if not cfg.enabled:
            return lat, lon, alt_m, True

        now = time.monotonic()

        # Check for active dropout
        if now < self._gps_dropout_until:
            return lat, lon, alt_m, False

        # Roll for new dropout
        if cfg.dropout_probability > 0 and self._rng.random() < cfg.dropout_probability:
            self._gps_dropout_until = now + cfg.dropout_duration_s
            return lat, lon, alt_m, False

        # Apply Gaussian position noise
        lat_offset_m = self._rng.gauss(0, cfg.horizontal_stddev_m)
        lon_offset_m = self._rng.gauss(0, cfg.horizontal_stddev_m)
        alt_offset_m = self._rng.gauss(0, cfg.vertical_stddev_m)

        lat_scale = 111_320.0  # meters per degree latitude
        lon_scale = max(1.0, math.cos(math.radians(lat)) * 111_320.0)

        return (
            lat + lat_offset_m / lat_scale,
            lon + lon_offset_m / lon_scale,
            max(0.0, alt_m + alt_offset_m),
            True,
        )

    # -- Sensor noise -------------------------------------------------------

    def apply_sensor_noise(self, alt_m: float, airspeed_mps: float) -> tuple[float, float]:
        """Apply additive sensor noise to altitude and airspeed.

        Returns (noisy_alt, noisy_airspeed). Airspeed is clamped to >= 0.
        """
        cfg = self._profile.sensors
        if not cfg.enabled:
            return alt_m, airspeed_mps

        noisy_alt = alt_m + self._rng.gauss(0, cfg.altitude_stddev_m)
        noisy_airspeed = max(0.0, airspeed_mps + self._rng.gauss(0, cfg.airspeed_stddev_mps))
        return noisy_alt, noisy_airspeed

    # -- Wind model ---------------------------------------------------------

    def compute_wind_effect(
        self, groundspeed_mps: float, heading_rad: float
    ) -> tuple[float, float]:
        """Compute wind effect on ground speed.

        Returns (effective_groundspeed, drift_heading_offset_rad).
        Headwind reduces ground speed, tailwind increases it.
        Crosswind introduces heading drift.
        """
        cfg = self._profile.wind
        if not cfg.enabled:
            return groundspeed_mps, 0.0

        now = time.monotonic()

        # Gust management
        gust_speed = 0.0
        if now < self._gust_until and self._active_gust is not None:
            gust_speed = self._active_gust[0]
        elif cfg.gust_probability > 0 and self._rng.random() < cfg.gust_probability:
            gust_mag = self._rng.uniform(0, cfg.gust_speed_mps)
            gust_heading = self._rng.uniform(0, 2 * math.pi)
            self._active_gust = (gust_mag, gust_heading)
            lo, hi = cfg.gust_duration_range_s
            self._gust_until = now + self._rng.uniform(lo, hi)
            gust_speed = gust_mag
        else:
            self._active_gust = None

        total_wind_speed = cfg.base_speed_mps + gust_speed
        wind_heading_rad = math.radians(cfg.base_heading_deg)

        # Decompose wind into head/tail and crosswind components
        headwind_component = total_wind_speed * math.cos(heading_rad - wind_heading_rad)
        crosswind_component = total_wind_speed * math.sin(heading_rad - wind_heading_rad)

        effective_gs = max(0.0, groundspeed_mps - headwind_component)
        drift = math.atan2(crosswind_component, max(groundspeed_mps, 1.0))

        return effective_gs, drift

    # -- Communication faults -----------------------------------------------

    def should_drop_command(self) -> bool:
        """Returns True if the current command should be silently dropped (comm loss)."""
        cfg = self._profile.comm
        if not cfg.enabled:
            return False

        now = time.monotonic()

        # Active sustained loss window
        if now < self._comm_loss_until:
            return True

        # Roll for new comm event
        if cfg.loss_probability > 0 and self._rng.random() < cfg.loss_probability:
            if cfg.loss_duration_s > 0:
                self._comm_loss_until = now + cfg.loss_duration_s
            return True

        return False

    def command_delay(self) -> float:
        """Returns the delay in seconds to apply before command execution.

        Models radio latency with jitter.
        """
        cfg = self._profile.comm
        if not cfg.enabled:
            return 0.0
        return max(0.0, cfg.base_delay_s + self._rng.gauss(0, cfg.jitter_s))

    # -- Battery model ------------------------------------------------------

    def compute_battery_drain(
        self,
        current_percent: float,
        dt: float,
        airspeed_mps: float,
        is_maneuvering: bool = False,
    ) -> float:
        """Compute non-linear battery drain.

        Returns the new battery percentage after dt seconds.
        Three-zone discharge: slow above 50%, medium 50-20%, rapid below 20%.
        Maneuvering (transitions, aggressive turns) adds voltage sag penalty.
        """
        cfg = self._profile.battery
        if not cfg.enabled:
            return current_percent  # caller handles linear drain

        if current_percent > 50.0:
            rate = cfg.high_drain_rate
        elif current_percent > 20.0:
            rate = cfg.mid_drain_rate
        else:
            rate = cfg.low_drain_rate

        sag = cfg.voltage_sag_factor if is_maneuvering else 0.0
        drain = (rate + sag) * dt * max(airspeed_mps, 2.0)
        return max(0.0, current_percent - drain)

    # -- Takeoff dynamics ---------------------------------------------------

    def compute_takeoff_altitude(
        self, target_alt_m: float, current_alt_m: float, dt: float
    ) -> tuple[float, bool]:
        """Compute realistic takeoff climb.

        Returns (new_altitude, has_reached_target).
        When disabled, returns (target_alt_m, True) for backward compatibility
        (instantaneous jump to target).
        """
        cfg = self._profile.takeoff
        if not cfg.enabled:
            return target_alt_m, True

        if self._takeoff_started_at is None:
            self._takeoff_started_at = time.monotonic()
            self._takeoff_climb_rate = cfg.initial_climb_rate_mps

        # Accelerate climb rate toward maximum
        self._takeoff_climb_rate = min(
            cfg.max_climb_rate_mps,
            self._takeoff_climb_rate + cfg.acceleration_mps2 * dt,
        )

        new_alt = current_alt_m + self._takeoff_climb_rate * dt
        reached = new_alt >= target_alt_m
        if reached:
            new_alt = target_alt_m
            self._takeoff_started_at = None
        return new_alt, reached

    def reset_takeoff(self) -> None:
        """Reset takeoff state (call after landing or abort)."""
        self._takeoff_started_at = None
        self._takeoff_climb_rate = 0.0
