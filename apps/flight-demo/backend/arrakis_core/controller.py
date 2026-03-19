from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Callable

from airframe_profile import AirframeProfile
from config import ARRAKIS_LINK_PROFILE
from arrakis_core.route_planner import build_route_preview
from flight_adapters.base import FlightControllerAdapter, VideoFrame, validate_adapter_contract
from schemas import RoutePreview, RouteRequest, TelemetrySnapshot

from .flight_event_recorder import FlightEventRecorder
from .mission_executor import MissionExecutor
from .mission_state_machine import INTERRUPT_PHASES, MissionStateMachine
from .state_payload_assembler import StatePayloadAssembler
from .state_snapshot_recorder import StateSnapshotRecorder
from .telemetry_hub import TelemetryHub
from .transition_diagnostics import TransitionDiagnosticsTracker
from .video_service import VideoService


logger = logging.getLogger("arrakis.controller")


class ArrakisController:
    def __init__(self, adapter: FlightControllerAdapter, profile: AirframeProfile) -> None:
        self.adapter = validate_adapter_contract(adapter)
        self.profile = profile
        self.state_machine = MissionStateMachine()
        self._mission_lock = threading.Lock()
        self._mission_thread: threading.Thread | None = None
        self._mission_cancel: threading.Event | None = None
        self.startup_error: str | None = None
        # Fix 14: concurrent abort protection
        self._abort_lock = threading.Lock()
        self._abort_in_progress = False
        self._last_telemetry_state: str | None = None
        self.snapshot_recorder = StateSnapshotRecorder()
        self.event_recorder = FlightEventRecorder(link_profile=ARRAKIS_LINK_PROFILE.name)
        self.adapter.set_event_sink(self.event_recorder.record_event)
        self.event_recorder.record_event(
            "session_start",
            adapter=self.adapter.__class__.__name__,
            airframe_profile=profile.name,
        )

        logger.info("Initializing controller with adapter=%s profile=%s", adapter.__class__.__name__, profile.name)
        try:
            self.adapter.connect()
        except Exception as exc:
            self.startup_error = f"{type(exc).__name__}: {exc}"
            self.event_recorder.record_event(
                "exception",
                source="controller.connect",
                exception_class=type(exc).__name__,
                message=str(exc),
            )
            logger.exception("Adapter connect failed during controller initialization: %s", exc)
        self.video_service = VideoService()
        self.telemetry_hub = TelemetryHub(self.adapter.get_snapshot(), self.video_service, profile)
        self.state_payload_assembler = StatePayloadAssembler(self.video_service)
        self.transition_diagnostics = TransitionDiagnosticsTracker()
        self.mission_executor = MissionExecutor(
            adapter=self.adapter,
            state_machine=self.state_machine,
            telemetry_hub=self.telemetry_hub,
            profile=profile,
        )
        self.adapter.stream_telemetry(self._on_telemetry)
        self.adapter.stream_video(self._on_video)
        bootstrap = self.adapter.bootstrap_status()
        self.event_recorder.record_event("bootstrap_status", bootstrap=bootstrap.model_dump(mode="json"))
        self.event_recorder.update_manifest(link_profile=bootstrap.link_profile)
        logger.info("Controller initialized and adapter streams subscribed startup_error=%s", self.startup_error)

    def set_route(self, preview: RoutePreview) -> RoutePreview:
        logger.info(
            "Setting route outbound=%d return=%d geofence_points=%d",
            len(preview.outbound),
            len(preview.return_path),
            len(preview.geofence.coordinates),
        )
        return self.state_machine.set_route(preview, self._mission_active())

    def build_route_preview(self, request: RouteRequest) -> RoutePreview:
        bootstrap = self.adapter.bootstrap_status()
        if bootstrap.control_plane_fault:
            raise RuntimeError(
                f"Vehicle control plane fault is active. Recover before setting route ({bootstrap.reason or 'unknown reason'})."
            )
        if not (bootstrap.telemetry_fresh and bootstrap.position_ready and bootstrap.home_ready):
            raise RuntimeError(
                f"Vehicle home/telemetry not ready. Wait before setting route ({bootstrap.reason or 'unknown reason'})."
            )
        runtime_home = self.adapter.get_home()
        if runtime_home != request.home:
            logger.info(
                "Overriding requested route home lat=%.6f lon=%.6f with vehicle home lat=%.6f lon=%.6f",
                request.home.lat,
                request.home.lon,
                runtime_home.lat,
                runtime_home.lon,
            )
        normalized_request = request.model_copy(update={"home": runtime_home})
        return build_route_preview(normalized_request, self.profile)

    def start_mission(self) -> None:
        bootstrap = self.adapter.bootstrap_status()
        if bootstrap.control_plane_fault:
            raise RuntimeError(
                f"Vehicle control plane fault is active. Recover before mission start ({bootstrap.reason or 'unknown reason'})."
            )
        if not bootstrap.mission_ready:
            raise RuntimeError(
                f"Vehicle telemetry bootstrap incomplete. Mission start is blocked ({bootstrap.reason or 'unknown reason'})."
            )
        self.state_machine.start_mission(self._mission_active())
        self.transition_diagnostics.reset()
        mission_id = uuid.uuid4().hex
        self.event_recorder.set_mission_id(mission_id)
        self.event_recorder.record_event(
            "mission_start_requested",
            mission_phase=self.state_machine.phase,
            bootstrap=bootstrap.model_dump(mode="json"),
        )
        cancel_event = threading.Event()
        mission_thread = threading.Thread(
            target=self._run_mission,
            args=(cancel_event,),
            daemon=True,
        )
        with self._mission_lock:
            self._mission_cancel = cancel_event
            self._mission_thread = mission_thread
        logger.info("Starting mission thread=%s", mission_thread.name)
        mission_thread.start()

    def abort(self, reason: str = "manual operator abort") -> None:
        logger.warning("Abort requested: %s", reason)
        self.event_recorder.record_event("abort_requested", reason=reason, mission_phase=self.state_machine.phase)
        if not self._guarded_abort("ABORT_MANUAL", reason, lambda: self.adapter.abort(reason)):
            logger.info("Abort already in progress, skipping duplicate abort for: %s", reason)
            return
        self._cancel_active_mission(join_timeout=1.5)

    def rtl(self) -> None:
        logger.warning("RTL requested")
        self.event_recorder.record_event("rtl_requested", mission_phase=self.state_machine.phase)
        self.state_machine.abort("RTL_BATTERY", "manual rtl requested")
        self.adapter.return_to_home()
        self._cancel_active_mission(join_timeout=1.5)

    def reset(self) -> None:
        logger.info("Reset requested")
        self.event_recorder.record_event("mission_reset_requested", mission_phase=self.state_machine.phase)
        if self._mission_active():
            try:
                self.adapter.abort("reset requested")
            except Exception as exc:
                self.event_recorder.record_event(
                    "exception",
                    source="controller.reset.abort",
                    exception_class=type(exc).__name__,
                    message=str(exc),
                )
                logger.exception("Adapter abort failed during reset: %s", exc)
            self._cancel_active_mission(join_timeout=3.0)
        self.adapter.reset()
        self.video_service.reset()
        self.telemetry_hub.reset(self.adapter.get_snapshot())
        self.transition_diagnostics.reset()
        self.state_machine.reset()
        # Fix 14: reset abort flag
        with self._abort_lock:
            self._abort_in_progress = False
        self.event_recorder.set_mission_id(None)
        logger.info("Reset complete")

    def shutdown(self) -> None:
        logger.info("Controller shutdown requested")
        try:
            self.reset()
        except Exception as exc:
            self.event_recorder.record_event(
                "exception",
                source="controller.shutdown.reset",
                exception_class=type(exc).__name__,
                message=str(exc),
            )
            logger.exception("Controller reset failed during shutdown: %s", exc)
        onboard_metadata = self._collect_postflight_log_metadata()
        self.event_recorder.record_event("session_end", mission_phase=self.state_machine.phase)
        self.event_recorder.close(onboard_log_metadata=onboard_metadata)
        self.snapshot_recorder.close()

    def recover_control_plane(self):
        self.event_recorder.record_event("control_plane_recover_requested", mission_phase=self.state_machine.phase)
        bootstrap = self.adapter.recover_control_plane()
        self.telemetry_hub.reset(self.adapter.get_snapshot())
        self.transition_diagnostics.reset()
        self.event_recorder.record_event("control_plane_recover_result", bootstrap=bootstrap.model_dump(mode="json"))
        return bootstrap

    def log_status(self) -> dict[str, str | None]:
        return {
            "event_log_path": self.event_recorder.event_log_path,
            "session_manifest_path": self.event_recorder.manifest_path,
        }

    def state_payload(self):
        payload = self._assemble_state_payload()
        self.snapshot_recorder.record(payload)
        return payload

    def latest_jpeg(self) -> bytes:
        return self.video_service.latest_jpeg()

    _SAFETY_SUPPRESS_PHASES = INTERRUPT_PHASES | {"LANDING", "COMPLETE", "IDLE", "STARTING"}

    def _on_telemetry(self, snapshot: TelemetrySnapshot) -> None:
        route_preview = self.state_machine.route_preview
        phase = self.state_machine.phase
        if snapshot.telemetry_state != self._last_telemetry_state:
            self.event_recorder.record_event(
                "telemetry_state_transition",
                previous_state=self._last_telemetry_state,
                telemetry_state=snapshot.telemetry_state,
                telemetry_age_s=snapshot.telemetry_age_s,
                mission_phase=phase,
            )
            self._last_telemetry_state = snapshot.telemetry_state
        decision = self.telemetry_hub.on_telemetry(snapshot, route_preview, phase)
        # Fix 14: safety triggers use _guarded_abort to prevent concurrent abort race conditions
        if decision.trigger_battery_rtl and phase not in self._SAFETY_SUPPRESS_PHASES:
            logger.warning("Battery RTL triggered at %.1f%% during phase=%s", snapshot.battery_percent, phase)
            self.event_recorder.record_event("safety_trigger", trigger="battery_rtl", mission_phase=phase)
            self._guarded_abort("RTL_BATTERY", "battery threshold reached", lambda: self.adapter.return_to_home())
        elif decision.trigger_position_loss_rtl and phase not in self._SAFETY_SUPPRESS_PHASES:
            logger.warning("GPS position lost during phase=%s, triggering RTL", phase)
            self.event_recorder.record_event("safety_trigger", trigger="position_loss_rtl", mission_phase=phase)
            self._guarded_abort("RTL_GPS_LOSS", "gps position lost during flight", lambda: self.adapter.return_to_home())
        elif decision.trigger_navigation_degraded_rtl and phase not in self._SAFETY_SUPPRESS_PHASES:
            logger.warning("Navigation degraded during phase=%s, triggering RTL", phase)
            self.event_recorder.record_event("safety_trigger", trigger="navigation_degraded_rtl", mission_phase=phase)
            self._guarded_abort("RTL_NAV_DEGRADED", "navigation degraded during flight", lambda: self.adapter.return_to_home())
        elif decision.trigger_geofence_abort and phase not in self._SAFETY_SUPPRESS_PHASES:
            logger.warning("Geofence abort triggered during phase=%s", phase)
            self.event_recorder.record_event("safety_trigger", trigger="geofence_abort", mission_phase=phase)
            self._guarded_abort("ABORT_GEOFENCE", "route-derived geofence breached", lambda: self.adapter.abort("geofence breach"))
        elif decision.trigger_telemetry_lost and phase not in self._SAFETY_SUPPRESS_PHASES:
            logger.warning("Telemetry lost during phase=%s, triggering RTL", phase)
            self.event_recorder.record_event("safety_trigger", trigger="telemetry_lost_rtl", mission_phase=phase)
            self._guarded_abort("RTL_LINK_LOSS", "telemetry data lost during flight", lambda: self.adapter.return_to_home())
        self.transition_diagnostics.observe(
            self.state_machine.phase,
            self.telemetry_hub.telemetry_snapshot(),
            self.state_machine.abort_reason,
        )
        self.snapshot_recorder.record(self._assemble_state_payload())

    # Fix 14: serialized abort to prevent concurrent abort race conditions
    def _guarded_abort(self, phase: str, reason: str, action: Callable) -> bool:
        """Execute an abort action with mutual exclusion.

        Returns True if this call performed the abort, False if an abort was
        already in progress (duplicate suppressed).
        """
        with self._abort_lock:
            if self._abort_in_progress:
                logger.info("Abort already in progress, suppressing duplicate phase=%s reason=%s", phase, reason)
                return False
            self._abort_in_progress = True
        try:
            self.state_machine.abort(phase, reason)
            self.event_recorder.record_event("abort_phase_entered", target_phase=phase, reason=reason)
            action()
        except Exception as exc:
            self.event_recorder.record_event(
                "exception",
                source="controller._guarded_abort",
                target_phase=phase,
                reason=reason,
                exception_class=type(exc).__name__,
                message=str(exc),
            )
            raise
        finally:
            # Auto-reset after 2 seconds (allow next abort if needed)
            def _reset_abort_flag():
                time.sleep(2.0)
                with self._abort_lock:
                    self._abort_in_progress = False
            threading.Thread(target=_reset_abort_flag, daemon=True).start()
        return True

    def _on_video(self, frame: VideoFrame) -> None:
        self.video_service.on_video(frame)

    def _assemble_state_payload(self):
        status = self.state_machine.snapshot()
        current_leg = self.adapter.current_leg()
        return self.state_payload_assembler.build(
            telemetry=self.telemetry_hub.telemetry_snapshot(),
            mission_phase=status.phase,
            abort_reason=status.abort_reason,
            route_preview=status.route_preview,
            current_leg=current_leg,
            transition=self.transition_diagnostics.snapshot(),
            stress=self.telemetry_hub.stress_envelope(),
        )

    def _run_mission(self, cancel_event: threading.Event) -> None:
        try:
            logger.info("Mission executor started")
            self.mission_executor.run_roundtrip_mission(cancel_event)
        except Exception as exc:
            logger.exception("Mission executor crashed: %s", exc)
            self.event_recorder.record_event(
                "exception",
                source="controller._run_mission",
                exception_class=type(exc).__name__,
                message=str(exc),
            )
            if self.state_machine.phase not in {"ABORT_MANUAL", "ABORT_GEOFENCE", "RTL_BATTERY", "RTL_LINK_LOSS", "RTL_GPS_LOSS", "RTL_NAV_DEGRADED", "COMPLETE"}:
                try:
                    self.adapter.return_to_home()
                except Exception as rtl_exc:
                    self.event_recorder.record_event(
                        "exception",
                        source="controller._run_mission.return_to_home",
                        exception_class=type(rtl_exc).__name__,
                        message=str(rtl_exc),
                    )
                    logger.exception("Mission fallback RTL failed: %s", rtl_exc)
                self.state_machine.abort("ABORT_MANUAL", f"mission executor failed: {exc}")
        finally:
            logger.info("Mission executor finished")
            self._clear_mission_thread(threading.current_thread())

    def _collect_postflight_log_metadata(self) -> dict[str, object] | None:
        wrapped = getattr(self.adapter, "wrapped", self.adapter)
        collector = getattr(wrapped, "postflight_log_metadata", None)
        if not callable(collector):
            return None
        try:
            metadata = collector()
            if metadata is not None:
                self.event_recorder.update_manifest(onboard_log_metadata=metadata)
            return metadata
        except Exception as exc:
            self.event_recorder.record_event(
                "exception",
                source="controller.postflight_log_metadata",
                exception_class=type(exc).__name__,
                message=str(exc),
            )
            logger.exception("Post-flight log metadata collection failed: %s", exc)
            return {"attempted": True, "status": "failed", "reason": str(exc)}

    def _mission_active(self) -> bool:
        with self._mission_lock:
            thread = self._mission_thread
            if thread is None:
                return False
            if thread.is_alive():
                return True
            self._mission_thread = None
            self._mission_cancel = None
            return False

    def _cancel_active_mission(self, join_timeout: float) -> None:
        with self._mission_lock:
            thread = self._mission_thread
            cancel_event = self._mission_cancel
        if cancel_event is not None:
            logger.info("Setting mission cancel event")
            cancel_event.set()
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            logger.info("Joining mission thread=%s timeout=%.1fs", thread.name, join_timeout)
            thread.join(timeout=join_timeout)
        self._clear_mission_thread(thread, only_if_inactive=True)

    def _clear_mission_thread(self, thread: threading.Thread | None, *, only_if_inactive: bool = False) -> None:
        with self._mission_lock:
            active_thread = self._mission_thread
            if active_thread is None:
                self._mission_cancel = None
                return
            if only_if_inactive and active_thread.is_alive():
                return
            if thread is not None and active_thread is not thread and active_thread.is_alive():
                return
            if thread is None and active_thread.is_alive():
                return
            if thread is None or active_thread is thread or not active_thread.is_alive():
                self._mission_thread = None
                self._mission_cancel = None
