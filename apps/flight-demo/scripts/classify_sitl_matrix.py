#!/usr/bin/env python3
"""Repeat SITL matrix scenarios and classify them as slow, flaky, or real failure.

Classification is based on run-time telemetry, not only pytest pass/fail:
 - time to outbound entry
 - airspeed / groundspeed profile
 - longest leg-stuck interval
 - whether RTL / landing was entered
 - whether the last telemetry window still showed progression

Usage:
  ./scripts/classify_sitl_matrix.py rc_no_channels combo_fence_wind --runs 3
  ./.venv/bin/python scripts/classify_sitl_matrix.py --runs 2 --json rc_no_channels
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Literal


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
TESTS_DIR = PROJECT_ROOT / "tests"

for candidate in (str(BACKEND_DIR), str(TESTS_DIR), str(PROJECT_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from airframe_profile import AirframeProfile
from conftest import force_arm_sitl, force_disarm_sitl, set_sitl_param
from flight_adapters.ardupilot import ArduPilotAdapter
from flight_adapters.instrumented import InstrumentedFlightAdapter
from test_sitl_deep import _build_short_mission, _save_and_restore_params
from test_sitl_matrix import (
    SCENARIO_MATRIX,
    ScenarioConfig,
    _clear_fence,
    _configure_legacy_geofence,
    _ensure_connection_healthy,
    _set_verified_param,
    _set_verified_params,
)


TakeoffThreshold = 15.0 * (1.0 - 0.3)
SampleBucket = Literal["pass", "slow", "failure", "infra"]
OverallBucket = Literal["stable_pass", "slow", "flaky", "real_failure", "infra"]

OUTBOUND_SLOW_THRESHOLD_S = 45.0
TERMINAL_SLOW_THRESHOLD_S = 90.0
FAILSAFE_RESPONSE_SLOW_THRESHOLD_S = 20.0
LEG_STUCK_THRESHOLD_S = 18.0
PROGRESS_HOME_DELTA_M = 8.0
PROGRESS_ALT_DELTA_M = 3.0
LOW_GROUNDSPEED_MPS = 4.0
HIGH_AIRSPEED_MPS = 12.0
TAIL_PROGRESS_WINDOW_S = 10.0
SAMPLE_INTERVAL_S = 0.5

LANDING_TEXT_MARKERS = (
    "Mission: 4 VTOLLand",
    "Reached waypoint",
    "Passed waypoint",
    "Land descend started",
    "Land final started",
    "Land complete",
)


@dataclass(frozen=True)
class TelemetryTraceSample:
    t_rel_s: float
    armed: bool
    flight_mode: str
    leg: str
    mission_index: int
    home_distance_m: float
    alt_m: float
    airspeed_mps: float
    groundspeed_mps: float
    statustext: str


@dataclass(frozen=True)
class WaitEvent:
    name: str
    timeout_s: float
    elapsed_s: float
    timed_out: bool


@dataclass(frozen=True)
class ScenarioRunMetrics:
    wall_clock_s: float
    duration_s: float
    sample_count: int
    pytest_timeout_budget_s: float | None
    runner_query_timeout_count: int
    max_runner_query_timeout_budget_s: float | None
    timed_out_runner_query: str | None
    timed_out_runner_query_timeout_s: float | None
    timed_out_runner_query_elapsed_s: float | None
    time_to_outbound_s: float | None
    time_to_return_s: float | None
    time_to_rtl_s: float | None
    time_to_landing_s: float | None
    time_to_disarm_s: float | None
    max_airspeed_mps: float
    min_airspeed_mps: float
    max_groundspeed_mps: float
    min_groundspeed_mps: float
    max_air_ground_gap_mps: float
    low_groundspeed_high_airspeed_seen: bool
    longest_stuck_leg_s: float
    longest_stuck_leg: str | None
    tail_progressing: bool
    tail_mission_index_delta: int
    tail_home_distance_delta_m: float
    tail_altitude_delta_m: float
    last_mode: str | None
    last_leg: str | None
    last_mission_index: int | None
    last_home_distance_m: float | None
    saw_expected_mode: bool
    saw_rtl: bool
    saw_landing: bool
    saw_outbound: bool
    saw_return: bool
    wait_events: list[WaitEvent]


@dataclass(frozen=True)
class ScenarioRunResult:
    scenario: str
    run_index: int
    bucket: SampleBucket
    subtype: str
    passed: bool
    detail: str
    metrics: ScenarioRunMetrics


@dataclass(frozen=True)
class ScenarioRepeatSummary:
    scenario: str
    overall_bucket: OverallBucket
    summary_reason: str
    runs: list[ScenarioRunResult]


class ScenarioExecutionError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ScenarioObserver:
    def __init__(self, adapter) -> None:
        self.adapter = adapter
        self.started_at = time.monotonic()
        self.samples: list[TelemetryTraceSample] = []
        self.outbound_at_s: float | None = None
        self.return_at_s: float | None = None
        self.rtl_at_s: float | None = None
        self.landing_at_s: float | None = None
        self.disarm_at_s: float | None = None
        self.last_trigger_at_s: float | None = None
        self.wait_events: list[WaitEvent] = []

    def mark_trigger(self) -> None:
        self.last_trigger_at_s = time.monotonic() - self.started_at

    def sample(self) -> TelemetryTraceSample:
        snap = self.adapter.get_snapshot()
        leg = self.adapter.current_leg()
        statustext = getattr(self.adapter, "_last_statustext", "") or ""
        now_rel = time.monotonic() - self.started_at
        sample = TelemetryTraceSample(
            t_rel_s=round(now_rel, 3),
            armed=snap.armed,
            flight_mode=snap.flight_mode,
            leg=leg,
            mission_index=snap.mission_index,
            home_distance_m=snap.home_distance_m,
            alt_m=snap.alt_m,
            airspeed_mps=snap.airspeed_mps,
            groundspeed_mps=snap.groundspeed_mps,
            statustext=statustext,
        )
        self.samples.append(sample)
        self._update_events(sample)
        return sample

    def sleep(self, duration_s: float) -> TelemetryTraceSample:
        deadline = time.monotonic() + duration_s
        latest = self.sample()
        while time.monotonic() < deadline:
            time.sleep(min(SAMPLE_INTERVAL_S, max(deadline - time.monotonic(), 0.0)))
            latest = self.sample()
        return latest

    def wait_until(self, name: str, predicate, timeout_s: float) -> TelemetryTraceSample | None:
        deadline = time.monotonic() + timeout_s
        started = time.monotonic()
        latest = self.sample()
        while True:
            if predicate(latest):
                self.wait_events.append(
                    WaitEvent(
                        name=name,
                        timeout_s=timeout_s,
                        elapsed_s=round(time.monotonic() - started, 3),
                        timed_out=False,
                    )
                )
                return latest
            if time.monotonic() >= deadline:
                self.wait_events.append(
                    WaitEvent(
                        name=name,
                        timeout_s=timeout_s,
                        elapsed_s=round(time.monotonic() - started, 3),
                        timed_out=True,
                    )
                )
                return None
            time.sleep(min(SAMPLE_INTERVAL_S, max(deadline - time.monotonic(), 0.0)))
            latest = self.sample()

    def wait_for_altitude(self, threshold_m: float, timeout_s: float) -> bool:
        return self.wait_until(
            f"wait_for_altitude>={threshold_m:.1f}m",
            lambda s: s.alt_m >= threshold_m,
            timeout_s,
        ) is not None

    def wait_for_leg(self, target_legs: set[str], timeout_s: float) -> str | None:
        hit = self.wait_until(
            f"wait_for_leg:{','.join(sorted(target_legs))}",
            lambda s: s.leg in target_legs,
            timeout_s,
        )
        return None if hit is None else hit.leg

    def wait_for_mode(self, modes: set[str], timeout_s: float) -> str | None:
        upper_modes = {mode.upper() for mode in modes}
        hit = self.wait_until(
            f"wait_for_mode:{','.join(sorted(upper_modes))}",
            lambda s: s.flight_mode.upper() in upper_modes,
            timeout_s,
        )
        return None if hit is None else hit.flight_mode

    def wait_for_disarm(self, timeout_s: float) -> bool:
        return self.wait_until("wait_for_disarm", lambda s: not s.armed, timeout_s) is not None

    def wait_for_completion_or_landing(self, timeout_s: float) -> bool:
        def _predicate(sample: TelemetryTraceSample) -> bool:
            if not sample.armed:
                return True
            if sample.leg == "landing":
                return True
            return any(marker in sample.statustext for marker in LANDING_TEXT_MARKERS)

        hit = self.wait_until("wait_for_completion_or_landing", _predicate, timeout_s)
        if hit is None:
            return False
        if hit.armed:
            force_disarm_sitl(self.adapter)
            self.sample()
        return True

    def _update_events(self, sample: TelemetryTraceSample) -> None:
        if self.outbound_at_s is None and sample.leg == "outbound":
            self.outbound_at_s = sample.t_rel_s
        if self.return_at_s is None and sample.leg == "return":
            self.return_at_s = sample.t_rel_s
        if self.rtl_at_s is None and sample.flight_mode.upper() in {"RTL", "QRTL"}:
            self.rtl_at_s = sample.t_rel_s
        if self.landing_at_s is None:
            if sample.leg == "landing" or any(marker in sample.statustext for marker in LANDING_TEXT_MARKERS):
                self.landing_at_s = sample.t_rel_s
        if self.disarm_at_s is None and self.samples and not sample.armed:
            armed_seen = any(previous.armed for previous in self.samples[:-1])
            if armed_seen:
                self.disarm_at_s = sample.t_rel_s


def _compute_longest_stuck_window(samples: list[TelemetryTraceSample]) -> tuple[float, str | None]:
    best_duration = 0.0
    best_leg: str | None = None
    segment_start: TelemetryTraceSample | None = None
    anchor: TelemetryTraceSample | None = None

    for sample in samples:
        eligible = sample.armed and sample.leg in {"takeoff", "outbound", "return", "landing"}
        if not eligible:
            segment_start = None
            anchor = None
            continue
        if segment_start is None or anchor is None:
            segment_start = sample
            anchor = sample
            continue
        progressed = (
            sample.leg != anchor.leg
            or sample.mission_index != anchor.mission_index
            or abs(sample.home_distance_m - anchor.home_distance_m) >= PROGRESS_HOME_DELTA_M
            or abs(sample.alt_m - anchor.alt_m) >= PROGRESS_ALT_DELTA_M
            or sample.flight_mode != anchor.flight_mode
        )
        if progressed:
            segment_start = sample
            anchor = sample
            continue
        duration = sample.t_rel_s - segment_start.t_rel_s
        if duration > best_duration:
            best_duration = duration
            best_leg = sample.leg
    return round(best_duration, 3), best_leg


def _tail_progression(samples: list[TelemetryTraceSample]) -> tuple[bool, int, float, float]:
    if not samples:
        return False, 0, 0.0, 0.0
    last = samples[-1]
    window_start_t = max(last.t_rel_s - TAIL_PROGRESS_WINDOW_S, 0.0)
    start = samples[0]
    for sample in samples:
        if sample.t_rel_s >= window_start_t:
            start = sample
            break
    mission_delta = last.mission_index - start.mission_index
    home_delta = last.home_distance_m - start.home_distance_m
    alt_delta = last.alt_m - start.alt_m
    progressed = (
        mission_delta != 0
        or abs(home_delta) >= PROGRESS_HOME_DELTA_M
        or abs(alt_delta) >= PROGRESS_ALT_DELTA_M
        or last.leg != start.leg
        or last.flight_mode != start.flight_mode
    )
    return progressed, mission_delta, round(home_delta, 3), round(alt_delta, 3)


def _build_metrics(
    observer: ScenarioObserver,
    scenario: ScenarioConfig,
    *,
    pytest_timeout_budget_s: float | None,
    wall_clock_s: float,
) -> ScenarioRunMetrics:
    samples = observer.samples
    if not samples:
        raise ScenarioExecutionError("no_telemetry", "No telemetry samples collected")
    longest_stuck_s, longest_stuck_leg = _compute_longest_stuck_window(samples)
    tail_progressing, tail_mission_delta, tail_home_delta, tail_alt_delta = _tail_progression(samples)
    timed_out_waits = [event for event in observer.wait_events if event.timed_out]
    first_timed_out_wait = timed_out_waits[0] if timed_out_waits else None

    airspeeds = [sample.airspeed_mps for sample in samples]
    groundspeeds = [sample.groundspeed_mps for sample in samples]
    max_gap = max(
        (sample.airspeed_mps - sample.groundspeed_mps for sample in samples),
        default=0.0,
    )
    low_groundspeed_high_airspeed_seen = any(
        sample.airspeed_mps >= HIGH_AIRSPEED_MPS and sample.groundspeed_mps <= LOW_GROUNDSPEED_MPS
        for sample in samples
    )
    saw_expected_mode = any(sample.flight_mode.upper() in {mode.upper() for mode in scenario.expect_modes} for sample in samples)
    return ScenarioRunMetrics(
        wall_clock_s=round(wall_clock_s, 3),
        duration_s=round(samples[-1].t_rel_s, 3),
        sample_count=len(samples),
        pytest_timeout_budget_s=pytest_timeout_budget_s,
        runner_query_timeout_count=len(timed_out_waits),
        max_runner_query_timeout_budget_s=max((event.timeout_s for event in observer.wait_events), default=None),
        timed_out_runner_query=None if first_timed_out_wait is None else first_timed_out_wait.name,
        timed_out_runner_query_timeout_s=None if first_timed_out_wait is None else first_timed_out_wait.timeout_s,
        timed_out_runner_query_elapsed_s=None if first_timed_out_wait is None else first_timed_out_wait.elapsed_s,
        time_to_outbound_s=observer.outbound_at_s,
        time_to_return_s=observer.return_at_s,
        time_to_rtl_s=observer.rtl_at_s,
        time_to_landing_s=observer.landing_at_s,
        time_to_disarm_s=observer.disarm_at_s,
        max_airspeed_mps=round(max(airspeeds), 3),
        min_airspeed_mps=round(min(airspeeds), 3),
        max_groundspeed_mps=round(max(groundspeeds), 3),
        min_groundspeed_mps=round(min(groundspeeds), 3),
        max_air_ground_gap_mps=round(max_gap, 3),
        low_groundspeed_high_airspeed_seen=low_groundspeed_high_airspeed_seen,
        longest_stuck_leg_s=longest_stuck_s,
        longest_stuck_leg=longest_stuck_leg,
        tail_progressing=tail_progressing,
        tail_mission_index_delta=tail_mission_delta,
        tail_home_distance_delta_m=tail_home_delta,
        tail_altitude_delta_m=tail_alt_delta,
        last_mode=samples[-1].flight_mode,
        last_leg=samples[-1].leg,
        last_mission_index=samples[-1].mission_index,
        last_home_distance_m=round(samples[-1].home_distance_m, 3),
        saw_expected_mode=saw_expected_mode,
        saw_rtl=observer.rtl_at_s is not None,
        saw_landing=observer.landing_at_s is not None,
        saw_outbound=observer.outbound_at_s is not None,
        saw_return=observer.return_at_s is not None,
        wait_events=list(observer.wait_events),
    )


def _classify_run(
    scenario: ScenarioConfig,
    metrics: ScenarioRunMetrics,
    *,
    execution_error: ScenarioExecutionError | None,
    trigger_at_s: float | None,
) -> tuple[SampleBucket, str, bool, str]:
    if execution_error is None:
        if scenario.expect_modes and trigger_at_s is not None and metrics.saw_expected_mode and metrics.time_to_rtl_s is not None:
            response_s = metrics.time_to_rtl_s - trigger_at_s
            if response_s > FAILSAFE_RESPONSE_SLOW_THRESHOLD_S:
                return (
                    "slow",
                    "slow_failsafe_response",
                    True,
                    f"Expected mode reached after {response_s:.1f}s from trigger",
                )
        if metrics.time_to_outbound_s is not None and metrics.time_to_outbound_s > OUTBOUND_SLOW_THRESHOLD_S:
            return (
                "slow",
                "slow_outbound_entry",
                True,
                f"Outbound entry took {metrics.time_to_outbound_s:.1f}s",
            )
        if metrics.time_to_disarm_s is not None and metrics.time_to_disarm_s > TERMINAL_SLOW_THRESHOLD_S:
            return (
                "slow",
                "slow_terminal_completion",
                True,
                f"Disarm took {metrics.time_to_disarm_s:.1f}s",
            )
        if metrics.time_to_landing_s is not None and metrics.time_to_landing_s > TERMINAL_SLOW_THRESHOLD_S:
            return (
                "slow",
                "slow_landing_entry",
                True,
                f"Landing entry took {metrics.time_to_landing_s:.1f}s",
            )
        return ("pass", "stable_pass", True, "Expectation met within thresholds")

    if execution_error.code in {"bootstrap_timeout", "connection_lost", "no_telemetry"}:
        return ("infra", execution_error.code, False, execution_error.detail)

    if execution_error.code == "takeoff_altitude_timeout":
        if metrics.longest_stuck_leg_s >= LEG_STUCK_THRESHOLD_S and not metrics.tail_progressing:
            return (
                "failure",
                "pre_outbound_stuck",
                False,
                f"Never reached takeoff altitude; stuck in {metrics.longest_stuck_leg} for {metrics.longest_stuck_leg_s:.1f}s",
            )
        return ("failure", "takeoff_failure", False, execution_error.detail)

    if execution_error.code == "missing_expected_mode":
        if metrics.saw_landing or metrics.saw_return or metrics.time_to_disarm_s is not None:
            return (
                "failure",
                "expected_mode_missing_but_progressed",
                False,
                f"Mission progressed to {metrics.last_leg}/{metrics.last_mode} without expected mode",
            )
        if metrics.longest_stuck_leg_s >= LEG_STUCK_THRESHOLD_S and not metrics.tail_progressing:
            return (
                "failure",
                "leg_stuck_before_expected_mode",
                False,
                f"Leg {metrics.longest_stuck_leg} was stuck for {metrics.longest_stuck_leg_s:.1f}s",
            )
        if not metrics.tail_progressing:
            return (
                "failure",
                "telemetry_progress_stalled",
                False,
                "Telemetry stopped showing mission progression in the last window",
            )
        return ("failure", "expected_mode_missing", False, execution_error.detail)

    if execution_error.code == "completion_timeout":
        if metrics.saw_landing or metrics.saw_rtl:
            return (
                "slow",
                "terminal_recovery_slow",
                False,
                f"Recovery entered ({metrics.last_mode}/{metrics.last_leg}) but completion timed out",
            )
        if metrics.longest_stuck_leg_s >= LEG_STUCK_THRESHOLD_S and not metrics.tail_progressing:
            return (
                "failure",
                "leg_stuck",
                False,
                f"Leg {metrics.longest_stuck_leg} was stuck for {metrics.longest_stuck_leg_s:.1f}s",
            )
        if metrics.time_to_outbound_s is None:
            return ("failure", "pre_outbound_no_entry", False, execution_error.detail)
        if metrics.tail_progressing:
            return (
                "slow",
                "progressing_but_not_terminal",
                False,
                "Telemetry still progressed in the final window, but terminal condition was not reached in time",
            )
        return ("failure", "terminal_recovery_missing", False, execution_error.detail)

    if execution_error.code == "invalid_mode":
        return ("failure", "invalid_mode", False, execution_error.detail)

    return ("failure", execution_error.code, False, execution_error.detail)


def _summarize_runs(scenario_name: str, runs: list[ScenarioRunResult]) -> ScenarioRepeatSummary:
    if not runs:
        raise RuntimeError("No run results to summarize")

    buckets = {run.bucket for run in runs}
    subtypes = {run.subtype for run in runs}

    if buckets == {"infra"}:
        return ScenarioRepeatSummary(
            scenario=scenario_name,
            overall_bucket="infra",
            summary_reason="All runs failed in setup/connection state",
            runs=runs,
        )

    if buckets <= {"pass"}:
        return ScenarioRepeatSummary(
            scenario=scenario_name,
            overall_bucket="stable_pass",
            summary_reason="All runs passed within thresholds",
            runs=runs,
        )

    if buckets <= {"slow"}:
        return ScenarioRepeatSummary(
            scenario=scenario_name,
            overall_bucket="slow",
            summary_reason="All runs met expectations but exceeded timing thresholds",
            runs=runs,
        )

    if buckets <= {"pass", "slow"}:
        return ScenarioRepeatSummary(
            scenario=scenario_name,
            overall_bucket="flaky",
            summary_reason="Runs alternated between thresholded slow and normal pass",
            runs=runs,
        )

    if "failure" in buckets and buckets <= {"failure"} and len(subtypes) == 1:
        return ScenarioRepeatSummary(
            scenario=scenario_name,
            overall_bucket="real_failure",
            summary_reason=f"All runs failed with the same subtype: {next(iter(subtypes))}",
            runs=runs,
        )

    return ScenarioRepeatSummary(
        scenario=scenario_name,
        overall_bucket="flaky",
        summary_reason="Runs produced mixed pass/slow/failure outcomes or mixed failure subtypes",
        runs=runs,
    )


def _wait_for_bootstrap(instrumented, timeout_s: float = 180.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        bootstrap = instrumented.bootstrap_status()
        if bootstrap.mission_ready:
            return
        time.sleep(1.0)
    raise ScenarioExecutionError("bootstrap_timeout", "Vehicle did not reach mission_ready before timeout")


def _run_scenario_once(
    adapter,
    instrumented,
    scenario: ScenarioConfig,
    run_index: int,
    *,
    pytest_timeout_budget_s: float | None,
) -> ScenarioRunResult:
    observer = ScenarioObserver(adapter)
    execution_error: ScenarioExecutionError | None = None
    run_started = time.monotonic()

    try:
        _ensure_connection_healthy(adapter, instrumented)
        observer.sample()
    except BaseException as exc:
        if isinstance(exc, ScenarioExecutionError):
            execution_error = exc
        else:
            execution_error = ScenarioExecutionError("connection_lost", str(exc))
    else:
        force_disarm_sitl(adapter)
        instrumented.reset()
        try:
            adapter._set_mode("QLOITER")
        except Exception:
            pass
        _clear_fence(adapter)
        try:
            _set_verified_param(adapter, "SIM_RC_FAIL", 0.0)
        except Exception:
            pass
        observer.sleep(2.0)

        params = scenario.to_param_dict()
        param_names = list(params.keys())
        if scenario.rc_fail:
            param_names.append("SIM_RC_FAIL")
        if scenario.gcs_failsafe:
            param_names.append("FS_GCS_ENABL")

        try:
            with _save_and_restore_params(adapter, param_names):
                _set_verified_params(adapter, params)
                if scenario.fence_enable:
                    _configure_legacy_geofence(adapter, scenario.fence_radius_m, scenario.fence_action)
                observer.sleep(1.0)

                if scenario.gps_enable == 0:
                    observer.sleep(3.0)
                    try:
                        adapter.arm()
                    except Exception:
                        pass
                    observer.sample()
                    force_disarm_sitl(adapter)
                else:
                    _build_short_mission(
                        adapter,
                        distance_m=scenario.distance_m,
                        bearing_deg=scenario.bearing_deg,
                    )
                    observer.sleep(1.0)

                    force_arm_sitl(adapter)
                    observer.sample()
                    adapter.start_mission()
                    observer.sample()

                    reached_alt = observer.wait_for_altitude(TakeoffThreshold, timeout_s=60.0)
                    if not reached_alt and scenario.exit_mode != "abort":
                        raise ScenarioExecutionError(
                            "takeoff_altitude_timeout",
                            f"[{scenario.name}] Failed to reach takeoff altitude",
                        )

                    if scenario.inject_delay_s > 0:
                        observer.sleep(scenario.inject_delay_s)
                    if scenario.rc_fail and "rc_" in scenario.name:
                        observer.mark_trigger()
                        _set_verified_param(adapter, "SIM_RC_FAIL", float(scenario.rc_fail))
                        observer.sleep(2.0)
                    if scenario.gcs_failsafe:
                        observer.mark_trigger()
                        observer.sleep(2.0)

                    if scenario.exit_mode == "abort":
                        observer.mark_trigger()
                        adapter.land_vertical()
                        observer.sample()
                    elif scenario.exit_mode == "rtl_outbound":
                        observer.wait_for_leg({"outbound"}, timeout_s=60.0)
                        observer.sleep(2.0)
                        observer.mark_trigger()
                        adapter.return_to_home()
                        observer.sample()
                    elif scenario.exit_mode == "rtl_return":
                        observer.wait_for_leg({"return"}, timeout_s=120.0)
                        observer.sleep(2.0)
                        observer.mark_trigger()
                        adapter.return_to_home()
                        observer.sample()
                    elif scenario.exit_mode == "force_disarm":
                        observer.mark_trigger()
                        force_disarm_sitl(adapter)
                        observer.sample()

                    if scenario.exit_mode == "force_disarm":
                        if adapter.get_snapshot().armed:
                            raise ScenarioExecutionError(
                                "force_disarm_failed",
                                f"[{scenario.name}] Expected disarmed after force_disarm",
                            )
                    elif scenario.expect_completion:
                        completed = observer.wait_for_completion_or_landing(timeout_s=20.0)
                        if not completed:
                            raise ScenarioExecutionError(
                                "completion_timeout",
                                f"[{scenario.name}] Mission did not complete within 20.0s",
                            )
                    elif scenario.expect_modes:
                        mode = observer.wait_for_mode(set(scenario.expect_modes), timeout_s=60.0)
                        if mode is None:
                            current = adapter.get_snapshot().flight_mode
                            raise ScenarioExecutionError(
                                "missing_expected_mode",
                                f"[{scenario.name}] Expected one of {scenario.expect_modes} but got {current}",
                            )
                        if not observer.wait_for_disarm(timeout_s=30.0):
                            force_disarm_sitl(adapter)
                            observer.sample()
                    else:
                        observer.sleep(5.0)
                        current = adapter.get_snapshot().flight_mode.upper()
                        if current in {"DISCONNECTED", "INITIALISING"}:
                            raise ScenarioExecutionError(
                                "invalid_mode",
                                f"[{scenario.name}] Vehicle entered invalid mode {current}",
                            )
        except ScenarioExecutionError as exc:
            execution_error = exc
        finally:
            try:
                if scenario.fence_enable:
                    _clear_fence(adapter)
            finally:
                force_disarm_sitl(adapter)
                observer.sample()
                observer.sleep(2.0)

    metrics = _build_metrics(
        observer,
        scenario,
        pytest_timeout_budget_s=pytest_timeout_budget_s,
        wall_clock_s=time.monotonic() - run_started,
    )
    bucket, subtype, passed, detail = _classify_run(
        scenario,
        metrics,
        execution_error=execution_error,
        trigger_at_s=observer.last_trigger_at_s,
    )
    return ScenarioRunResult(
        scenario=scenario.name,
        run_index=run_index,
        bucket=bucket,
        subtype=subtype,
        passed=passed,
        detail=detail,
        metrics=metrics,
    )


def _format_run(result: ScenarioRunResult) -> str:
    metrics = result.metrics
    runner_timeout = (
        f"{metrics.timed_out_runner_query}@{metrics.timed_out_runner_query_timeout_s}s"
        if metrics.timed_out_runner_query is not None
        else "none"
    )
    return (
        f"run={result.run_index} bucket={result.bucket} subtype={result.subtype} "
        f"pytest_budget={metrics.pytest_timeout_budget_s} "
        f"runner_timeout={runner_timeout} wall={metrics.wall_clock_s:.1f}s "
        f"outbound={metrics.time_to_outbound_s} rtl={metrics.time_to_rtl_s} "
        f"landing={metrics.time_to_landing_s} disarm={metrics.time_to_disarm_s} "
        f"stuck={metrics.longest_stuck_leg_s:.1f}s/{metrics.longest_stuck_leg} "
        f"airspeed=[{metrics.min_airspeed_mps:.1f},{metrics.max_airspeed_mps:.1f}] "
        f"groundspeed=[{metrics.min_groundspeed_mps:.1f},{metrics.max_groundspeed_mps:.1f}] "
        f"tail_progress={metrics.tail_progressing} "
        f"last={metrics.last_leg}/{metrics.last_mode}/wp{metrics.last_mission_index} "
        f"detail={result.detail}"
    )


def _summary_to_dict(summary: ScenarioRepeatSummary) -> dict[str, object]:
    return {
        "scenario": summary.scenario,
        "overall_bucket": summary.overall_bucket,
        "summary_reason": summary.summary_reason,
        "mean_duration_s": round(mean(run.metrics.duration_s for run in summary.runs), 3),
        "runs": [
            {
                "scenario": run.scenario,
                "run_index": run.run_index,
                "bucket": run.bucket,
                "subtype": run.subtype,
                "passed": run.passed,
                "detail": run.detail,
                "metrics": asdict(run.metrics),
            }
            for run in summary.runs
        ],
    }


def _default_pytest_timeout_budget() -> float | None:
    explicit = os.getenv("ARRAKIS_PYTEST_TIMEOUT_BUDGET_S")
    if explicit:
        return float(explicit)

    addopts = os.getenv("PYTEST_ADDOPTS", "")
    match = re.search(r"--timeout(?:=|\\s+)(\\d+(?:\\.\\d+)?)", addopts)
    if match:
        return float(match.group(1))

    return 600.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenarios", nargs="+", help="Scenario names from tests/test_sitl_matrix.py")
    parser.add_argument("--runs", type=int, default=3, help="How many repetitions per scenario")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument(
        "--pytest-timeout-budget",
        type=float,
        default=_default_pytest_timeout_budget(),
        help="Track pytest-internal timeout budget separately from runner query timeouts",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    scenario_map = {scenario.name: scenario for scenario in SCENARIO_MATRIX}
    unknown = [name for name in args.scenarios if name not in scenario_map]
    if unknown:
        print(f"Unknown scenarios: {', '.join(unknown)}", file=sys.stderr)
        return 2

    profile = AirframeProfile()
    adapter = ArduPilotAdapter(profile)
    instrumented = InstrumentedFlightAdapter(adapter, logger_name="arrakis.sitl.classifier")
    summaries: list[ScenarioRepeatSummary] = []

    try:
        instrumented.connect()
        _wait_for_bootstrap(instrumented)
        try:
            set_sitl_param(adapter, "ARMING_CHECK", 0)
        except Exception:
            pass

        for scenario_name in args.scenarios:
            scenario = scenario_map[scenario_name]
            runs: list[ScenarioRunResult] = []
            for run_index in range(1, args.runs + 1):
                runs.append(
                    _run_scenario_once(
                        adapter,
                        instrumented,
                        scenario,
                        run_index,
                        pytest_timeout_budget_s=args.pytest_timeout_budget,
                    )
                )
            summaries.append(_summarize_runs(scenario.name, runs))
    finally:
        try:
            force_disarm_sitl(adapter)
        except Exception:
            pass
        try:
            adapter._running = False
        except Exception:
            pass
        try:
            if adapter._master is not None:
                adapter._master.close()
        except Exception:
            pass

    if args.json:
        print(json.dumps([_summary_to_dict(summary) for summary in summaries], indent=2))
    else:
        for summary in summaries:
            print(
                f"{summary.scenario}: overall={summary.overall_bucket} "
                f"reason={summary.summary_reason}"
            )
            for run in summary.runs:
                print(f"  {_format_run(run)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
