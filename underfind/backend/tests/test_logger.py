from __future__ import annotations

import logging
from underfind.backend.core.logger import logger, TRACE_LEVEL, UnderfindLogger


def test_logger_instance():
    assert isinstance(logger, UnderfindLogger)
    assert logger.name == "underfind"


def test_logger_trace_level_registered():
    assert logging.getLevelName(TRACE_LEVEL) == "TRACE"
    assert TRACE_LEVEL == 5


def test_logger_methods_callable():
    logger.setLevel(TRACE_LEVEL)
    logger.trace("Testing trace level output")
    logger.debug("Testing debug level output")
    logger.info("Testing info level output")
    logger.warning("Testing warning level output")
    logger.error("Testing error level output")
    logger.critical("Testing critical redirect to error")


def test_logger_critical_redirects_to_error(monkeypatch):
    error_called = []

    def mock_error(msg, *args, **kwargs):
        error_called.append(msg)

    monkeypatch.setattr(logger, "error", mock_error)
    logger.critical("Critical error occurred")

    assert len(error_called) == 1
    assert error_called[0] == "Critical error occurred"
