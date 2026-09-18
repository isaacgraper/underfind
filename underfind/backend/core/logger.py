from __future__ import annotations

import logging
import os
import sys
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

TRACE_LEVEL = 5
logging.addLevelName(TRACE_LEVEL, "TRACE")


class UnderfindLogger(logging.Logger):
    """
    Centralized singleton logger for Underfind v2.1.
    Includes TRACE (level 5) for tracing response payloads,
    DEBUG for outgoing requests, and treats CRITICAL as ERROR.
    """

    def trace(
        self,
        msg: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if self.isEnabledFor(TRACE_LEVEL):
            self._log(TRACE_LEVEL, msg, args, **kwargs)

    def critical(
        self,
        msg: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Any critical event is treated strictly as an error per system design."""
        self.error(msg, *args, **kwargs)


logging.setLoggerClass(UnderfindLogger)

_raw_level = os.environ.get("LOG_LEVEL", "INFO").upper()
_level_map = {
    "TRACE": TRACE_LEVEL,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.ERROR,
}
_active_level = _level_map.get(_raw_level, logging.INFO)

_console = Console(stderr=True)
_handler = RichHandler(
    console=_console,
    show_path=False,
    omit_repeated_times=False,
    rich_tracebacks=True,
)

logger: UnderfindLogger = logging.getLogger("underfind")  # type: ignore
logger.setLevel(_active_level)

if not logger.handlers:
    logger.addHandler(_handler)

logger.propagate = False
