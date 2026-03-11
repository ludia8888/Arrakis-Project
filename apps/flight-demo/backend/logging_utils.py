from __future__ import annotations

import logging

from config import LOG_LEVEL


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(LOG_LEVEL)
        return
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
