from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from config import EVENT_LOG_PATH, STATE_DUMP_PATH


logger = logging.getLogger("arrakis.events")


class FlightEventRecorder:
    def __init__(self, *, link_profile: str) -> None:
        self._lock = threading.Lock()
        self._closed = False
        self._root = Path(EVENT_LOG_PATH).expanduser()
        self._root.mkdir(parents=True, exist_ok=True)
        self.session_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        self._event_path = self._root / f"{self.session_id}.events.jsonl"
        self._manifest_path = self._root / f"{self.session_id}.manifest.json"
        self._file = self._event_path.open("a", encoding="utf-8")
        self._mission_id: str | None = None
        self._manifest: dict[str, Any] = {
            "session_id": self.session_id,
            "mission_id": None,
            "link_profile": link_profile,
            "created_at": time.time(),
            "event_log_path": str(self._event_path),
            "state_dump_path": STATE_DUMP_PATH,
            "onboard_log_metadata": None,
        }
        self._write_manifest_locked()
        logger.info("Flight event recorder enabled at %s", self._event_path)

    @property
    def event_log_path(self) -> str:
        return str(self._event_path)

    @property
    def manifest_path(self) -> str:
        return str(self._manifest_path)

    @property
    def mission_id(self) -> str | None:
        with self._lock:
            return self._mission_id

    def set_mission_id(self, mission_id: str | None) -> None:
        with self._lock:
            self._mission_id = mission_id
            self._manifest["mission_id"] = mission_id
            self._write_manifest_locked()

    def update_manifest(self, **fields: Any) -> None:
        with self._lock:
            self._manifest.update(fields)
            self._write_manifest_locked()

    def record_event(self, event_type: str, fields: dict[str, Any] | None = None, **extra: Any) -> None:
        payload = dict(fields or {})
        payload.update(extra)
        with self._lock:
            if self._closed:
                return
            event = {
                "event_type": event_type,
                "timestamp": time.time(),
                "monotonic": time.monotonic(),
                "session_id": self.session_id,
                "mission_id": self._mission_id,
                "link_profile": self._manifest["link_profile"],
                **payload,
            }
            self._write_line_locked(event)

    def close(self, *, onboard_log_metadata: dict[str, Any] | None = None) -> None:
        with self._lock:
            if self._closed:
                return
            if onboard_log_metadata is not None:
                self._manifest["onboard_log_metadata"] = onboard_log_metadata
            self._manifest["closed_at"] = time.time()
            self._write_manifest_locked()
            self._file.close()
            self._closed = True
            logger.info("Flight event recorder closed")

    def _write_line_locked(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        self._file.write(line)
        self._file.write("\n")
        self._file.flush()
        os.fsync(self._file.fileno())

    def _write_manifest_locked(self) -> None:
        temp_path = self._manifest_path.with_suffix(".manifest.json.tmp")
        data = json.dumps(self._manifest, ensure_ascii=True, sort_keys=True, indent=2)
        with temp_path.open("w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(self._manifest_path)
