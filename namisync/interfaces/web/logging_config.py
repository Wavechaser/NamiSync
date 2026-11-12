"""Bounded file logging for the headed NamiSync process."""

from __future__ import annotations

import importlib.metadata
import logging
import logging.handlers
import platform
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Callable

from namisync.version import VERSION

from .paths import AppPaths


_LOG_BYTES = 5 * 1024 * 1024
_LOG_BACKUPS = 5
_LOGGER_NAMES = ("namisync", "pywebview")
_DEPENDENCIES = (
    ("pywebview", "pywebview"),
    ("pythonnet", "pythonnet"),
    ("clr_loader", "clr-loader"),
    ("bottle", "bottle"),
)


class _UtcFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        del datefmt
        value = datetime.fromtimestamp(record.created, UTC)
        return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


class _OwnedRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """A later diagnostic write failure must not affect application truth."""

    def handleError(self, record: logging.LogRecord) -> None:
        del record


_FORMATTER = _UtcFormatter(
    "%(asctime)s %(levelname)s pid=%(process)d thread=%(threadName)s "
    "logger=%(name)s: %(message)s"
)
_state_lock = threading.RLock()
_handler: _OwnedRotatingFileHandler | None = None
_log_path: Path | None = None
_original_sys_hook: Callable[..., object] | None = None
_original_thread_hook: Callable[..., object] | None = None
_sys_hook_wrapper: Callable[..., object] | None = None
_thread_hook_wrapper: Callable[..., object] | None = None


def configure_logging(paths: AppPaths) -> Path:
    """Eagerly configure one shared GUI log handler and exception hooks."""

    global _handler, _log_path

    try:
        paths.ensure_directories()
    except OSError as error:
        raise RuntimeError(
            "NamiSync could not create its GUI data and log directories"
        ) from error
    expected_path = paths.log_file.resolve(strict=False)
    with _state_lock:
        if _handler is not None:
            if _log_path != expected_path:
                raise RuntimeError("GUI logging is already configured for another root")
            _configure_loggers(_handler)
            _install_exception_hooks()
            return expected_path

        try:
            handler = _OwnedRotatingFileHandler(
                expected_path,
                mode="a",
                maxBytes=_LOG_BYTES,
                backupCount=_LOG_BACKUPS,
                encoding="utf-8",
                delay=False,
                errors="backslashreplace",
            )
        except (OSError, ValueError) as error:
            raise RuntimeError("NamiSync could not create or open its GUI log") from error
        handler.setLevel(logging.INFO)
        handler.setFormatter(_FORMATTER)

        _handler = handler
        _log_path = expected_path
        _configure_loggers(handler)
        _install_exception_hooks()

    logging.getLogger("namisync").info(
        "startup.begin product_version=%s python_version=%s os_version=%s",
        VERSION,
        platform.python_version(),
        platform.platform(),
    )
    return expected_path


def log_startup_dependencies() -> None:
    """Record installed host dependency versions without importing them."""

    versions = [
        f"{label}={_distribution_version(distribution)}"
        for label, distribution in _DEPENDENCIES
    ]
    logging.getLogger("namisync").info("startup.dependencies %s", " ".join(versions))


def log_startup_renderer(browser_version: str) -> None:
    """Record the selected native WebView2 renderer identity."""

    logging.getLogger("namisync").info(
        "startup.renderer browser_version=%s",
        browser_version,
    )


def log_startup_failure(error: Exception) -> None:
    """Record one decisive post-configuration startup failure."""

    logging.getLogger("namisync").error(
        "startup.failed exception_type=%s",
        type(error).__name__,
        exc_info=(type(error), error, error.__traceback__),
    )


def shutdown_logging() -> None:
    """Emit the normal-exit record and close logging after the GUI loop."""

    with _state_lock:
        if _handler is None:
            return
        logging.getLogger("namisync").info("shutdown.complete")
    logging.shutdown()
    _release_configuration(close_handler=False)


def record_late_cleanup_failure(
    log_path: Path,
    event: str,
    error: Exception,
) -> None:
    """Best-effort one bounded record after the shared handler has closed."""

    handler: _OwnedRotatingFileHandler | None = None
    try:
        handler = _OwnedRotatingFileHandler(
            Path(log_path),
            mode="a",
            maxBytes=_LOG_BYTES,
            backupCount=_LOG_BACKUPS,
            encoding="utf-8",
            delay=False,
            errors="backslashreplace",
        )
        handler.setLevel(logging.ERROR)
        handler.setFormatter(_FORMATTER)
        record = logging.LogRecord(
            "namisync",
            logging.ERROR,
            __file__,
            0,
            "%s exception_type=%s",
            (event, type(error).__name__),
            None,
        )
        handler.handle(record)
    except Exception:
        return
    finally:
        if handler is not None:
            try:
                handler.close()
            except Exception:
                pass


def _distribution_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def _configure_loggers(handler: logging.Handler) -> None:
    for name in _LOGGER_NAMES:
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if handler not in logger.handlers:
            logger.addHandler(handler)


def _install_exception_hooks() -> None:
    global _original_sys_hook, _original_thread_hook
    global _sys_hook_wrapper, _thread_hook_wrapper

    if _sys_hook_wrapper is None:
        original_sys_hook = sys.excepthook

        def process_hook(
            exc_type: type[BaseException],
            exc_value: BaseException,
            traceback: TracebackType | None,
        ) -> None:
            try:
                logging.getLogger("namisync").critical(
                    "unhandled.process exception_type=%s",
                    exc_type.__name__,
                    exc_info=(exc_type, exc_value, traceback),
                )
            finally:
                original_sys_hook(exc_type, exc_value, traceback)

        _original_sys_hook = original_sys_hook
        _sys_hook_wrapper = process_hook
        sys.excepthook = process_hook

    if _thread_hook_wrapper is None:
        original_thread_hook = threading.excepthook

        def thread_hook(args: threading.ExceptHookArgs) -> None:
            try:
                logging.getLogger("namisync").critical(
                    "unhandled.thread exception_type=%s",
                    args.exc_type.__name__,
                    exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
                )
            finally:
                original_thread_hook(args)

        _original_thread_hook = original_thread_hook
        _thread_hook_wrapper = thread_hook
        threading.excepthook = thread_hook


def _release_configuration(*, close_handler: bool) -> None:
    global _handler, _log_path
    global _original_sys_hook, _original_thread_hook
    global _sys_hook_wrapper, _thread_hook_wrapper

    with _state_lock:
        handler = _handler
        if handler is not None:
            for name in _LOGGER_NAMES:
                logging.getLogger(name).removeHandler(handler)
            if close_handler:
                handler.close()

        if _sys_hook_wrapper is not None and sys.excepthook is _sys_hook_wrapper:
            assert _original_sys_hook is not None
            sys.excepthook = _original_sys_hook
        if (
            _thread_hook_wrapper is not None
            and threading.excepthook is _thread_hook_wrapper
        ):
            assert _original_thread_hook is not None
            threading.excepthook = _original_thread_hook

        _handler = None
        _log_path = None
        _original_sys_hook = None
        _original_thread_hook = None
        _sys_hook_wrapper = None
        _thread_hook_wrapper = None


def _reset_logging_for_tests() -> None:
    """Release module-owned state without closing unrelated process logging."""

    _release_configuration(close_handler=True)
