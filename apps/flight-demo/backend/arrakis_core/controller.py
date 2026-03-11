from __future__ import annotations

import logging
import threading
from contextlib import suppress

from arrakis_core.route_planner import build_route_preview
from flight_adapters.base import FlightControllerAdapter, VideoFrame, validate_adapter_contract
from schemas import RoutePreview, RouteRequest, TelemetrySnapshot

from .mission_executor import MissionExecutor
from .mission_state_machine import MissionStateMachine
from .state_payload_assembler import StatePayloadAssembler
from .state_snapshot_recorder import StateSnapshotRecorder
from .telemetry_hub import TelemetryHub
from .video_service import VideoService


logger = logging.getLogger("arrakis.controller")


class ArrakisController:
    def __init__(self, adapter: FlightControllerAdapter) -> None:
        self.adapter = validate_adapter_contract(adapter)
        self.state_machine = MissionStateMachine()
        self._mission_lock = threading.Lock()
        self._mission_thread: threading.Thread | None = None
        self._mission_cancel: threading.Event | None = None

        logger.info("Initializing controller with adapter=%s", adapter.__class__.__name__)
        self.adapter.connect()
        self.video_service = VideoService()
        self.telemetry_hub = TelemetryHub(self.adapter.get_snapshot(), self.video_service)
        self.state_payload_assembler = StatePayloadAssembler(self.video_service)
        self.snapshot_recorder = StateSnapshotRecorder()
        self.mission_executor = MissionExecutor(
            adapter=self.adapter,
            state_machine=self.state_machine,
            telemetry_hub=self.telemetry_hub,
        )
        self.adapter.stream_telemetry(self._on_telemetry)
        self.adapter.stream_video(self._on_video)
        logger.info("Controller initialized and adapter streams subscribed")

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
        return build_route_preview(normalized_request)

    def start_mission(self) -> None:
        bootstrap = self.adapter.bootstrap_status()
        if not bootstrap.mission_ready:
            raise RuntimeError(
                f"Vehicle telemetry bootstrap incomplete. Mission start is blocked ({bootstrap.reason or 'unknown reason'})."
            )
        self.state_machine.start_mission(self._mission_active())
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
        self.state_machine.abort("ABORT_MANUAL", reason)
        self.adapter.abort(reason)
        self._cancel_active_mission(join_timeout=1.5)

    def rtl(self) -> None:
        logger.warning("RTL requested")
        self.state_machine.abort("RTL_BATTERY", "manual rtl requested")
        self.adapter.return_to_home()
        self._cancel_active_mission(join_timeout=1.5)

    def reset(self) -> None:
        logger.info("Reset requested")
        if self._mission_active():
            with suppress(Exception):
                self.adapter.abort("reset requested")
            self._cancel_active_mission(join_timeout=3.0)
        self.adapter.reset()
        self.video_service.reset()
        self.telemetry_hub.reset(self.adapter.get_snapshot())
        self.state_machine.reset()
        logger.info("Reset complete")

    def shutdown(self) -> None:
        logger.info("Controller shutdown requested")
        with suppress(Exception):
            self.reset()
        self.snapshot_recorder.close()

    def state_payload(self):
        payload = self._assemble_state_payload()
        self.snapshot_recorder.record(payload)
        return payload

    def latest_jpeg(self) -> bytes:
        return self.video_service.latest_jpeg()

    def _on_telemetry(self, snapshot: TelemetrySnapshot) -> None:
        route_preview = self.state_machine.route_preview
        decision = self.telemetry_hub.on_telemetry(snapshot, route_preview)
        phase = self.state_machine.phase
        if decision.trigger_battery_rtl and phase not in {"RTL_BATTERY", "LANDING", "COMPLETE"}:
            logger.warning("Battery RTL triggered at %.1f%% during phase=%s", snapshot.battery_percent, phase)
            self.state_machine.abort("RTL_BATTERY", "battery threshold reached")
            self.adapter.return_to_home()
        if decision.trigger_geofence_abort and phase not in {"ABORT_GEOFENCE", "LANDING", "COMPLETE"}:
            logger.warning("Geofence abort triggered during phase=%s", phase)
            self.state_machine.abort("ABORT_GEOFENCE", "route-derived geofence breached")
            self.adapter.abort("geofence breach")
        self.snapshot_recorder.record(self._assemble_state_payload())

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
        )

    def _run_mission(self, cancel_event: threading.Event) -> None:
        try:
            logger.info("Mission executor started")
            self.mission_executor.run_roundtrip_mission(cancel_event)
        except Exception as exc:
            logger.exception("Mission executor crashed: %s", exc)
            if self.state_machine.phase not in {"ABORT_MANUAL", "ABORT_GEOFENCE", "RTL_BATTERY", "COMPLETE"}:
                self.state_machine.abort("ABORT_MANUAL", f"mission executor failed: {exc}")
        finally:
            logger.info("Mission executor finished")
            self._clear_mission_thread(threading.current_thread())

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
