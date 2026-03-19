from __future__ import annotations

import logging
import threading
import time

from schemas import MissionPhase, TelemetrySnapshot, TransitionDiagnostics


logger = logging.getLogger("arrakis.transition")

WATCH_PHASES = {"RETURN", "PRE_MC_RECOVERY", "TRANSITION_MC", "LANDING"}
TERMINAL_PHASES = {
    "COMPLETE",
    "ABORT_GEOFENCE",
    "ABORT_MANUAL",
    "RTL_BATTERY",
    "RTL_LINK_LOSS",
    "RTL_GPS_LOSS",
    "RTL_NAV_DEGRADED",
}


class TransitionDiagnosticsTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot = TransitionDiagnostics(
            active=False,
            started_at=None,
            finished_at=None,
            duration_s=None,
            entry_phase=None,
            entry_mode=None,
            landing_entry_mode=None,
            completion=None,
            min_airspeed_mps=None,
            max_airspeed_mps=None,
            min_home_distance_m=None,
            max_alt_m=None,
            samples=0,
        )

    def reset(self) -> None:
        with self._lock:
            self._snapshot = self._empty()
        logger.info("Transition diagnostics reset")

    def snapshot(self) -> TransitionDiagnostics:
        with self._lock:
            return self._snapshot

    def observe(self, phase: MissionPhase, telemetry: TelemetrySnapshot, abort_reason: str | None) -> None:
        with self._lock:
            current = self._snapshot

            if not current.active and phase in WATCH_PHASES:
                now = time.time()
                current = TransitionDiagnostics(
                    active=True,
                    started_at=now,
                    finished_at=None,
                    duration_s=0.0,
                    entry_phase=phase,
                    entry_mode=telemetry.flight_mode,
                    landing_entry_mode=telemetry.flight_mode if phase == "LANDING" else None,
                    completion=None,
                    min_airspeed_mps=telemetry.airspeed_mps,
                    max_airspeed_mps=telemetry.airspeed_mps,
                    min_home_distance_m=telemetry.home_distance_m,
                    max_alt_m=telemetry.alt_m,
                    samples=1,
                )
                self._snapshot = current
                logger.info(
                    "Transition diagnostics started phase=%s mode=%s airspeed=%.2f home_distance=%.1f alt=%.1f",
                    phase,
                    telemetry.flight_mode,
                    telemetry.airspeed_mps,
                    telemetry.home_distance_m,
                    telemetry.alt_m,
                )
                return

            if not current.active:
                return

            current = current.model_copy(
                update={
                    "duration_s": max(0.0, time.time() - (current.started_at or time.time())),
                    "min_airspeed_mps": _min_or_value(current.min_airspeed_mps, telemetry.airspeed_mps),
                    "max_airspeed_mps": _max_or_value(current.max_airspeed_mps, telemetry.airspeed_mps),
                    "min_home_distance_m": _min_or_value(current.min_home_distance_m, telemetry.home_distance_m),
                    "max_alt_m": _max_or_value(current.max_alt_m, telemetry.alt_m),
                    "samples": current.samples + 1,
                }
            )

            if phase == "LANDING" and current.landing_entry_mode is None:
                current = current.model_copy(update={"landing_entry_mode": telemetry.flight_mode})

            if phase in TERMINAL_PHASES:
                completion = phase if abort_reason is None else f"{phase}: {abort_reason}"
                current = current.model_copy(
                    update={
                        "active": False,
                        "finished_at": time.time(),
                        "duration_s": max(0.0, time.time() - (current.started_at or time.time())),
                        "completion": completion,
                    }
                )
                logger.info(
                    "Transition diagnostics completed completion=%s duration=%.1fs min_airspeed=%.2f min_home_distance=%.1f max_alt=%.1f",
                    completion,
                    current.duration_s or 0.0,
                    current.min_airspeed_mps or 0.0,
                    current.min_home_distance_m or 0.0,
                    current.max_alt_m or 0.0,
                )

            self._snapshot = current

    def _empty(self) -> TransitionDiagnostics:
        return TransitionDiagnostics(
            active=False,
            started_at=None,
            finished_at=None,
            duration_s=None,
            entry_phase=None,
            entry_mode=None,
            landing_entry_mode=None,
            completion=None,
            min_airspeed_mps=None,
            max_airspeed_mps=None,
            min_home_distance_m=None,
            max_alt_m=None,
            samples=0,
        )


def _min_or_value(current: float | None, value: float) -> float:
    return value if current is None else min(current, value)


def _max_or_value(current: float | None, value: float) -> float:
    return value if current is None else max(current, value)
