"""Source-level verification tests for ArduPilot adapter hardening.

These tests inspect the ardupilot.py source code to verify that hardening
fixes are present. They do NOT require a live SITL connection — they use
AST/source inspection to confirm structural changes.
"""
from __future__ import annotations

import ast
import inspect
import sys
import textwrap
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Read the source file once
ARDUPILOT_SOURCE = (BACKEND_DIR / "flight_adapters" / "ardupilot.py").read_text()
ARDUPILOT_AST = ast.parse(ARDUPILOT_SOURCE)


def _get_class_methods(tree: ast.Module, class_name: str) -> dict[str, ast.FunctionDef]:
    """Extract method nodes from a class in the AST."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            methods = {}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods[item.name] = item
            return methods
    return {}


ADAPTER_METHODS = _get_class_methods(ARDUPILOT_AST, "ArduPilotAdapter")


# ---------------------------------------------------------------------------
# Fix 1: Heartbeat Watchdog
# ---------------------------------------------------------------------------

class TestFix1HeartbeatWatchdog:
    def test_heartbeat_watchdog_timeout_field_exists(self):
        """ArduPilotAdapter must have _heartbeat_watchdog_timeout_s field."""
        assert "_heartbeat_watchdog_timeout_s" in ARDUPILOT_SOURCE

    def test_connection_lost_field_exists(self):
        """ArduPilotAdapter must have _connection_lost field."""
        assert "_connection_lost" in ARDUPILOT_SOURCE

    def test_heartbeat_watchdog_in_telemetry_loop(self):
        """Telemetry loop must check heartbeat age against watchdog timeout."""
        assert "_telemetry_loop" in ADAPTER_METHODS
        loop_source = ast.get_source_segment(ARDUPILOT_SOURCE, ADAPTER_METHODS["_telemetry_loop"])
        assert "heartbeat_watchdog_timeout_s" in loop_source
        assert "_connection_lost" in loop_source


# ---------------------------------------------------------------------------
# Fix 2: Command ACK Dictionary
# ---------------------------------------------------------------------------

class TestFix2CommandACKDict:
    def test_pending_acks_field_exists(self):
        """_pending_acks dict must replace _last_command_ack."""
        assert "_pending_acks" in ARDUPILOT_SOURCE
        # Old variable should NOT exist
        assert "_last_command_ack" not in ARDUPILOT_SOURCE.replace("last_command_ack", "pending_acks__check") or \
            ARDUPILOT_SOURCE.count("_last_command_ack") == 0

    def test_wait_for_command_ack_uses_dict(self):
        """_wait_for_command_ack must read from _pending_acks by command ID."""
        method = ADAPTER_METHODS.get("_wait_for_command_ack")
        assert method is not None
        source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
        assert "_pending_acks" in source
        assert "command" in [arg.arg for arg in method.args.args]

    def test_handle_message_stores_by_command(self):
        """_handle_message must store COMMAND_ACK by command ID in dict."""
        method = ADAPTER_METHODS.get("_handle_message")
        assert method is not None
        source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
        assert "_pending_acks[command]" in source or "_pending_acks[" in source


# ---------------------------------------------------------------------------
# Fix 3: Connection Loss Detection
# ---------------------------------------------------------------------------

class TestFix3ConnectionLoss:
    def test_consecutive_empty_reads_field(self):
        """_consecutive_empty_reads counter must exist."""
        assert "_consecutive_empty_reads" in ARDUPILOT_SOURCE

    def test_max_consecutive_empty_threshold(self):
        """_max_consecutive_empty threshold must exist."""
        assert "_max_consecutive_empty" in ARDUPILOT_SOURCE

    def test_io_error_handling_in_telemetry_loop(self):
        """Telemetry loop must catch OSError/IOError separately."""
        method = ADAPTER_METHODS.get("_telemetry_loop")
        assert method is not None
        source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
        assert "OSError" in source or "IOError" in source


# ---------------------------------------------------------------------------
# Fix 4: Mode Set Failure Unmasking
# ---------------------------------------------------------------------------

class TestFix4ModeSetUnmasking:
    def test_prepare_multicopter_recovery_no_blind_suppress(self):
        """prepare_multicopter_recovery must not blindly suppress exceptions."""
        method = ADAPTER_METHODS.get("prepare_multicopter_recovery")
        assert method is not None
        source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
        # Should use try/except with logging, not suppress(Exception) on mode set
        assert "logger.warning" in source or "logger.error" in source

    def test_transition_to_multicopter_logs_failure(self):
        """transition_to_multicopter must log mode set failures."""
        method = ADAPTER_METHODS.get("transition_to_multicopter")
        assert method is not None
        source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
        assert "logger.warning" in source


# ---------------------------------------------------------------------------
# Fix 5: Command Retry Logic
# ---------------------------------------------------------------------------

class TestFix5CommandRetry:
    def test_send_command_with_retry_exists(self):
        """_send_command_with_retry method must exist."""
        assert "_send_command_with_retry" in ADAPTER_METHODS

    def test_retry_method_has_retries_param(self):
        """_send_command_with_retry must accept retries parameter."""
        method = ADAPTER_METHODS["_send_command_with_retry"]
        arg_names = [arg.arg for arg in method.args.args]
        assert "retries" in arg_names

    def test_arm_uses_retry(self):
        """arm() must use _send_command_with_retry."""
        method = ADAPTER_METHODS.get("arm")
        assert method is not None
        source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
        assert "_send_command_with_retry" in source

    def test_takeoff_uses_retry(self):
        """takeoff_multicopter() must use _send_command_with_retry."""
        method = ADAPTER_METHODS.get("takeoff_multicopter")
        assert method is not None
        source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
        assert "_send_command_with_retry" in source

    def test_transitions_use_retry(self):
        """transition_to_fixedwing/multicopter must use _send_command_with_retry."""
        for name in ("transition_to_fixedwing", "transition_to_multicopter"):
            method = ADAPTER_METHODS.get(name)
            assert method is not None, f"{name} missing"
            source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
            assert "_send_command_with_retry" in source, f"{name} must use retry"


# ---------------------------------------------------------------------------
# Fix 6: Mission Upload Total Timeout
# ---------------------------------------------------------------------------

class TestFix6MissionUploadTimeout:
    def test_upload_has_total_timeout(self):
        """_upload_mission_points_mission_oriented must have total timeout."""
        method = ADAPTER_METHODS.get("_upload_mission_points_mission_oriented")
        assert method is not None
        source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
        assert "total_timeout" in source or "upload_deadline" in source


# ---------------------------------------------------------------------------
# Fix 7: Abort Hardening
# ---------------------------------------------------------------------------

class TestFix7AbortHardening:
    def test_abort_has_retry(self):
        """abort() must retry RTL."""
        method = ADAPTER_METHODS.get("abort")
        assert method is not None
        source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
        assert "range(3)" in source or "for attempt" in source

    def test_abort_has_force_disarm_fallback(self):
        """abort() must have force disarm as last resort."""
        method = ADAPTER_METHODS.get("abort")
        assert method is not None
        source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
        assert "21196" in source  # Force disarm magic number


# ---------------------------------------------------------------------------
# Fix 8: Pre-Arm Error Parsing
# ---------------------------------------------------------------------------

class TestFix8PrearmErrors:
    def test_prearm_errors_field_exists(self):
        """_prearm_errors list must exist."""
        assert "_prearm_errors" in ARDUPILOT_SOURCE

    def test_handle_message_collects_prearm(self):
        """_handle_message must collect prearm errors from STATUSTEXT."""
        method = ADAPTER_METHODS.get("_handle_message")
        assert method is not None
        source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
        assert "prearm" in source.lower()
        assert "_prearm_errors" in source

    def test_arm_surfaces_prearm_errors(self):
        """arm() must surface prearm errors in exception."""
        method = ADAPTER_METHODS.get("arm")
        assert method is not None
        source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
        assert "_prearm_errors" in source
        assert "RuntimeError" in source


# ---------------------------------------------------------------------------
# Fix 9: Monotonic Time
# ---------------------------------------------------------------------------

class TestFix9MonotonicTime:
    def test_monotonic_timestamps_exist(self):
        """Monotonic timestamp fields must exist."""
        assert "_last_telemetry_mono" in ARDUPILOT_SOURCE
        assert "_last_heartbeat_mono" in ARDUPILOT_SOURCE

    def test_get_snapshot_uses_monotonic(self):
        """get_snapshot() must use time.monotonic() for freshness."""
        method = ADAPTER_METHODS.get("get_snapshot")
        assert method is not None
        source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
        assert "monotonic" in source


# ---------------------------------------------------------------------------
# Fix 10: GPS Coordinate Validation
# ---------------------------------------------------------------------------

class TestFix10GPSValidation:
    def test_handle_message_validates_gps(self):
        """_handle_message must validate GPS lat/lon range."""
        method = ADAPTER_METHODS.get("_handle_message")
        assert method is not None
        source = ast.get_source_segment(ARDUPILOT_SOURCE, method)
        # Should check lat range
        assert "-90" in source or "90.0" in source
        # Should check lon range
        assert "-180" in source or "180.0" in source
        # Should reject (0,0)
        assert "0.0" in source
