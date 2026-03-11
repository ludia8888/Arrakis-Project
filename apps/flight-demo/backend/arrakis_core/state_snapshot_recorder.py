from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from config import STATE_DUMP_PATH
from schemas import StatePayload


logger = logging.getLogger("arrakis.snapshot")


class StateSnapshotRecorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._file = None
        if not STATE_DUMP_PATH:
            logger.info("State snapshot recorder disabled")
            return
        path = Path(STATE_DUMP_PATH).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("a", encoding="utf-8")
        logger.info("State snapshot recorder enabled at %s", path)

    def record(self, payload: StatePayload) -> None:
        if self._file is None:
            return
        line = json.dumps(payload.model_dump(mode="json"), ensure_ascii=True)
        with self._lock:
            self._file.write(line)
            self._file.write("\n")
            self._file.flush()

    def close(self) -> None:
        with self._lock:
            if self._file is not None:
                self._file.close()
                self._file = None
                logger.info("State snapshot recorder closed")
