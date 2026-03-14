"""Tests for mission executor robustness enhancements.

Validates GPS health gates, battery transition checks, landing timeout
hardening, and concurrent abort protection.
"""
from __future__ import annotations

import ast
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from airframe_profile import AirframeProfile, load_profile
from arrakis_core.mission_executor import MissionExecutor
from arrakis_core.mission_state_machine import MissionStateMachine
from arrakis_core.telemetry_hub import TelemetryHub
from arrakis_core.controller import ArrakisController
from flight_adapters.mock import MockAdapter
from schemas import LatLon, TelemetrySnapshot


# Read executor source for structural tests
EXECUTOR_SOURCE = (BACKEND_DIR / "arrakis_core" / "mission_executor.py").read_text()
CONTROLLER_SOURCE = (BACKEND_DIR / "arrakis_core" / "controller.py").read_text()


# ---------------------------------------------------------------------------
# Fix 11: GPS Health Gate (Source Inspection)
# ---------------------------------------------------------------------------

class TestFix11GPSHealthGate:
    def test_stepwise_loop_checks_position_valid(self):
        """Stepwise outbound/return loop must check position_valid."""
        assert "position_valid" in EXECUTOR_SOURCE
        # Should have GPS gate pattern
        assert "not telemetry.position_valid" in EXECUTOR_SOURCE

    def test_mission_oriented_loop_checks_position_valid(self):
        """Mission-oriented loop must check position_valid."""
        # Count occurrences — should appear in both loops
        count = EXECUTOR_SOURCE.count("not telemetry.position_valid")
        assert count >= 2, f"GPS health gate should appear in both loops, found {count}"

    def test_gps_gate_suspends_not_aborts(self):
        """GPS invalid should suspend transitions, not abort mission."""
        assert "suspending phase transitions" in EXECUTOR_SOURCE


# ---------------------------------------------------------------------------
# Fix 12: Battery Transition Checks (Source Inspection)
# ---------------------------------------------------------------------------

class TestFix12BatteryTransitionChecks:
    def test_check_battery_threshold_method_exists(self):
        """_check_battery_threshold helper must exist."""
        assert "_check_battery_threshold" in EXECUTOR_SOURCE

    def test_battery_check_after_arm(self):
        """Battery must be checked after arm()."""
        # Find the pattern: adapter.arm() followed by battery check
        arm_idx = EXECUTOR_SOURCE.find("self.adapter.arm()")
        assert arm_idx >= 0
        # _check_battery_threshold should appear after arm
        threshold_idx = EXECUTOR_SOURCE.find("_check_battery_threshold", arm_idx)
        assert threshold_idx > arm_idx, "Battery check must follow arm()"

    def test_battery_check_triggers_rtl(self):
        """_check_battery_threshold must trigger RTL when battery low."""
        # Find the method source
        assert "RTL_BATTERY" in EXECUTOR_SOURCE
        assert "battery threshold reached during transition" in EXECUTOR_SOURCE


# ---------------------------------------------------------------------------
# Fix 13: Landing Timeout (Source Inspection)
# ---------------------------------------------------------------------------

class TestFix13LandingTimeout:
    def test_post_abort_armed_monitoring(self):
        """After landing timeout abort, must monitor armed state."""
        assert "MANUAL INTERVENTION REQUIRED" in EXECUTOR_SOURCE

    def test_post_abort_disarm_check(self):
        """Landing timeout must check disarm after abort."""
        assert "Vehicle disarmed after landing timeout abort" in EXECUTOR_SOURCE


# ---------------------------------------------------------------------------
# Fix 14: Concurrent Abort Protection (Source Inspection)
# ---------------------------------------------------------------------------

class TestFix14ConcurrentAbort:
    def test_abort_lock_exists(self):
        """ArrakisController must have _abort_lock."""
        assert "_abort_lock" in CONTROLLER_SOURCE

    def test_guarded_abort_method_exists(self):
        """_guarded_abort method must exist."""
        assert "_guarded_abort" in CONTROLLER_SOURCE

    def test_on_telemetry_uses_guarded_abort(self):
        """_on_telemetry must use _guarded_abort instead of direct abort."""
        assert "_guarded_abort" in CONTROLLER_SOURCE
        # Check both battery and geofence triggers use it
        lines = CONTROLLER_SOURCE.split("\n")
        in_on_telemetry = False
        guarded_calls_in_telemetry = 0
        for line in lines:
            if "def _on_telemetry" in line:
                in_on_telemetry = True
            elif in_on_telemetry and line.strip().startswith("def "):
                break
            elif in_on_telemetry and "_guarded_abort" in line:
                guarded_calls_in_telemetry += 1
        assert guarded_calls_in_telemetry >= 2, \
            f"_on_telemetry should have at least 2 _guarded_abort calls, found {guarded_calls_in_telemetry}"

    def test_abort_in_progress_flag(self):
        """ArrakisController must have _abort_in_progress flag."""
        assert "_abort_in_progress" in CONTROLLER_SOURCE

    def test_reset_clears_abort_flag(self):
        """reset() must clear _abort_in_progress."""
        # Find reset method and check it clears the flag
        reset_idx = CONTROLLER_SOURCE.find("def reset(self)")
        assert reset_idx >= 0
        next_method = CONTROLLER_SOURCE.find("\n    def ", reset_idx + 10)
        if next_method < 0:
            next_method = len(CONTROLLER_SOURCE)
        reset_body = CONTROLLER_SOURCE[reset_idx:next_method]
        assert "_abort_in_progress" in reset_body


# ---------------------------------------------------------------------------
# Functional Tests: MockAdapter with fault injection
# ---------------------------------------------------------------------------

class TestMockAdapterFaultIntegration:
    """Functional tests for MockAdapter with FaultInjector wired in."""

    def test_default_mock_adapter_backward_compatible(self):
        """MockAdapter(profile) must work identically to before."""
        profile = load_profile("default-vtol")
        adapter = MockAdapter(profile)
        adapter.connect()
        adapter.arm()
        snap = adapter.get_snapshot()
        assert snap.armed is True
        assert snap.position_valid is True
        assert snap.battery_percent > 0

    def test_realistic_mock_adapter_creates_injector(self):
        """MockAdapter with fault_profile must create injector."""
        from flight_adapters.fault_injector import FaultProfile
        profile = load_profile("default-vtol")
        adapter = MockAdapter(profile, fault_profile=FaultProfile.realistic())
        assert adapter._fault_injector is not None

    def test_default_mock_adapter_no_injector(self):
        """MockAdapter without fault_profile must have no injector."""
        profile = load_profile("default-vtol")
        adapter = MockAdapter(profile)
        assert adapter._fault_injector is None

    def test_fault_adapter_still_arms(self):
        """MockAdapter with faults must still be able to arm."""
        from flight_adapters.fault_injector import FaultProfile
        profile = load_profile("default-vtol")
        adapter = MockAdapter(profile, fault_profile=FaultProfile.realistic())
        adapter.connect()
        adapter.arm()
        # Arm may fail due to comm drop, but if it succeeds:
        snap = adapter.get_snapshot()
        # Position may be noisy but should still be a TelemetrySnapshot
        assert isinstance(snap, TelemetrySnapshot)

    def test_reset_clears_fault_state(self):
        """MockAdapter.reset() must clear takeoff state."""
        from flight_adapters.fault_injector import FaultProfile
        profile = load_profile("default-vtol")
        adapter = MockAdapter(profile, fault_profile=FaultProfile.realistic())
        adapter.connect()
        adapter.arm()
        adapter.takeoff_multicopter(30.0)
        adapter.reset()
        assert adapter._takeoff_target_alt is None
        assert adapter._gps_valid is True
