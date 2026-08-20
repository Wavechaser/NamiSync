"""Bounded GUI logging contract tests."""

from __future__ import annotations

import importlib.metadata
import json
import logging
import os
import platform
import re
import subprocess
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

import namisync.interfaces.web.logging_config as logging_config
from namisync.interfaces.web.paths import AppPaths
from namisync.version import NICKNAME, VERSION


PROJECT_ROOT = Path(__file__).parents[3]
HEADER = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z "
    r"[A-Z]+ pid=\d+ thread=[^ ]+ logger=[^:]+: .+$"
)


@pytest.fixture(autouse=True)
def isolated_logging() -> None:
    logging_config._reset_logging_for_tests()
    yield
    logging_config._reset_logging_for_tests()


def _flush() -> None:
    assert logging_config._handler is not None
    logging_config._handler.flush()


def test_sh_g_3_configure_twice_owns_one_handler_hooks_and_logger_policy(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app")
    root = logging.getLogger()
    root_state = (tuple(root.handlers), root.level, root.propagate)
    logger_handlers: dict[str, tuple[logging.Handler, ...]] = {}
    foreign_handlers: dict[str, logging.Handler] = {}
    for name in ("namisync", "pywebview"):
        logger = logging.getLogger(name)
        logger_handlers[name] = tuple(logger.handlers)
        foreign = logging.NullHandler()
        foreign_handlers[name] = foreign
        logger.addHandler(foreign)
    prior_sys_hook = sys.excepthook
    prior_thread_hook = threading.excepthook

    try:
        first = logging_config.configure_logging(paths)
        handler = logging_config._handler
        process_wrapper = sys.excepthook
        thread_wrapper = threading.excepthook
        second = logging_config.configure_logging(paths)

        assert first == second == paths.log_file.resolve()
        assert paths.log_file.is_file()
        assert handler is not None
        assert logging_config._handler is handler
        assert handler.delay is False
        assert handler.maxBytes == 5 * 1024 * 1024
        assert handler.backupCount == 5
        assert handler.encoding.lower().replace("-", "") == "utf8"
        assert handler.errors == "backslashreplace"
        assert handler.level == logging.INFO
        for name in ("namisync", "pywebview"):
            logger = logging.getLogger(name)
            assert logger.level == logging.INFO
            assert logger.propagate is False
            assert tuple(logger.handlers) == (
                *logger_handlers[name],
                foreign_handlers[name],
                handler,
            )
        assert (tuple(root.handlers), root.level, root.propagate) == root_state
        assert sys.excepthook is not prior_sys_hook
        assert threading.excepthook is not prior_thread_hook
        assert sys.excepthook is process_wrapper
        assert threading.excepthook is thread_wrapper
    finally:
        for name, foreign in foreign_handlers.items():
            logging.getLogger(name).removeHandler(foreign)


def test_sh_g_3_child_gui_path_emits_exact_startup_and_dependency_records(
    tmp_path: Path,
) -> None:
    root = tmp_path / "child-app"
    script = """
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path.cwd() / "tests" / "interfaces" / "web"))

from _startup_test_support import (
    StartupHandshakeDocumentChannel,
    drive_startup_handshake,
)
from namisync.interfaces import launcher
from namisync.interfaces.web import host
from namisync.interfaces.web.paths import AppPaths


class Hook:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def emit(self):
        for handler in tuple(self.handlers):
            handler()


class Window:
    def __init__(self):
        self.real_url = "http://127.0.0.1:41700/assets/index.html"
        self.events = SimpleNamespace(
            before_load=Hook(),
            closing=Hook(),
            loaded=Hook(),
        )
        self.dom = SimpleNamespace(
            get_element=lambda selector: (
                SimpleNamespace(text="Ready")
                if selector == "#host-status"
                else None
            )
        )
        self.exposed_functions = ()

    def expose(self, *functions):
        self.exposed_functions = functions

    def destroy(self):
        pass


class Webview:
    def __init__(self):
        self.window = Window()

    def create_window(
        self,
        _title,
        _url,
        *,
        js_api,
        background_color,
        transparent,
        width,
        height,
        min_size,
    ):
        assert js_api is None
        assert background_color == "#F3F3F3"
        assert transparent is False
        assert width == 1280
        assert height == 800
        assert min_size == (1024, 640)
        return self.window


class LeaseNative:
    def close_handle(self, _handle):
        pass


class Service:
    def validate_database_contracts(self):
        return SimpleNamespace(state="ready", reason=None, reset_direction=None)

    def start_plan(self, *_args, **_kwargs):
        raise AssertionError("planning is outside this startup witness")

    def close(self):
        return SimpleNamespace(complete=True, unfinished=(), custody_released=True)


class Appearance:
    def __init__(self):
        self.surface_settlements = 0

    def request_initial_surface_settlement(self, callback):
        self.surface_settlements += 1
        callback(None)

    def close(self):
        pass


webview = Webview()
appearance = Appearance()


lease = host.DesktopInstanceLease(object(), LeaseNative())
host.acquire_desktop_instance = lambda _identity, native=None: (
    host.DesktopInstanceAdmission(lease, False, None)
)


def load_webview():
    assert (Path(sys.argv[1]) / "logs" / "namisync.log").is_file()
    return webview


def configure_security(window, url, document, _renderer_callback):
    assert window is webview.window
    document._mark_attached(url)
    logging.getLogger("pywebview").warning("child-renderer-record")


def start_webview(webview_module, *, on_initialized, storage_path):
    assert webview_module is webview
    assert Path(storage_path) == Path(sys.argv[1]) / "webview2"
    on_initialized()
    drive_startup_handshake(webview.window)


host._load_webview = load_webview
AppPaths.acquire_lease = lambda self: SimpleNamespace(
    bind_databases=lambda: None,
    close=lambda: None,
)
host._prepare_webview_host = lambda _module: None
host._create_service = lambda _paths: Service()
host._configure_window_security = configure_security
host._opaque_window_background = lambda _initial: "#F3F3F3"
host._configure_window_appearance = lambda _window, *_args: appearance
host._document_channel = StartupHandshakeDocumentChannel
host._start_webview = start_webview
startup_errors = []
launcher._report_startup_error = startup_errors.append

assert launcher.gui_main(["--data-dir", sys.argv[1]]) == 0
assert appearance.surface_settlements == 1
assert startup_errors == []
    """
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    started_at = datetime.now(UTC) - timedelta(milliseconds=1)
    completed = subprocess.run(
        [sys.executable, "-c", script, str(root)],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    finished_at = datetime.now(UTC) + timedelta(milliseconds=1)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout == ""
    assert completed.stderr == ""
    log_path = root / "logs" / "namisync.log"
    assert log_path.is_file()
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    assert all(HEADER.fullmatch(line) for line in lines)
    for line in lines:
        timestamp = line.split(" ", 1)[0]
        parsed = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f%z")
        assert parsed.utcoffset() == timedelta(0)
        assert started_at <= parsed <= finished_at

    startup = next(line for line in lines if "startup.begin" in line)
    assert f"product_version={VERSION}" in startup
    assert f"python_version={platform.python_version()}" in startup
    assert f"os_version={platform.platform()}" in startup
    assert NICKNAME not in startup
    assert any(
        line.endswith("logger=pywebview: child-renderer-record") for line in lines
    )
    dependencies = next(
        line for line in lines if "startup.dependencies" in line
    )
    for label, distribution in (
        ("pywebview", "pywebview"),
        ("pythonnet", "pythonnet"),
        ("clr_loader", "clr-loader"),
        ("bottle", "bottle"),
    ):
        assert f"{label}={importlib.metadata.version(distribution)}" in dependencies


def test_emitted_records_have_exact_header_and_version_only_startup(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app")
    logging_config.configure_logging(paths)
    logging.getLogger("pywebview").warning("renderer-message")
    _flush()

    lines = paths.log_file.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    assert all(HEADER.fullmatch(line) for line in lines)
    assert "startup.begin" in lines[0]
    assert f"product_version={VERSION}" in lines[0]
    assert "python_version=" in lines[0]
    assert "os_version=" in lines[0]
    assert NICKNAME not in lines[0]
    assert lines[1].endswith("logger=pywebview: renderer-message")


def test_post_configuration_startup_failure_records_type_and_traceback_once(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app")
    logging_config.configure_logging(paths)

    try:
        raise RuntimeError("synthetic startup failure")
    except RuntimeError as error:
        logging_config.log_startup_failure(error)
    _flush()

    text = paths.log_file.read_text(encoding="utf-8")
    assert text.count("startup.failed exception_type=RuntimeError") == 1
    assert "Traceback (most recent call last):" in text
    assert "RuntimeError: synthetic startup failure" in text


def test_dependency_record_reads_distribution_metadata_without_importing_hosts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app")
    seen: list[str] = []

    def version(name: str) -> str:
        seen.append(name)
        return f"installed-{name}"

    monkeypatch.setattr(logging_config.importlib.metadata, "version", version)
    logging_config.configure_logging(paths)
    before = set(sys.modules)

    logging_config.log_startup_dependencies()
    _flush()

    assert seen == ["pywebview", "pythonnet", "clr-loader", "bottle"]
    assert set(sys.modules) == before
    text = paths.log_file.read_text(encoding="utf-8")
    assert "startup.dependencies" in text
    assert "pywebview=installed-pywebview" in text
    assert "pythonnet=installed-pythonnet" in text
    assert "clr_loader=installed-clr-loader" in text
    assert "bottle=installed-bottle" in text


def test_sh_g_3_ascii_rollover_creates_the_numbered_backup(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app")
    logging_config.configure_logging(paths)
    handler = logging_config._handler
    assert handler is not None
    handler.maxBytes = 5 * 1024
    logger = logging.getLogger("namisync.test")

    logger.info("before-rollover %s", "a" * (3 * 1024))
    logger.info("after-rollover %s", "b" * (3 * 1024))
    _flush()

    backup = paths.logs / "namisync.log.1"
    assert backup.is_file()
    assert "before-rollover" in backup.read_text(encoding="utf-8")
    assert "after-rollover" in paths.log_file.read_text(encoding="utf-8")


def test_sh_g_3_unicode_and_surrogate_fallback_emit_without_internal_error(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app")
    logging_config.configure_logging(paths)
    logger = logging.getLogger("namisync.test")

    logger.info("snowman=\N{SNOWMAN}")
    logger.info("surrogate=\udcff")
    _flush()

    payload = b"".join(path.read_bytes() for path in paths.logs.iterdir())
    decoded = payload.decode("utf-8")
    assert "snowman=\N{SNOWMAN}" in decoded
    assert r"surrogate=\udcff" in decoded


def test_sh_g_3_process_hook_logs_once_and_delegates_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process_calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(sys, "excepthook", lambda *args: process_calls.append(args))
    paths = AppPaths.from_root(tmp_path / "app")
    logging_config.configure_logging(paths)
    process_hook = sys.excepthook
    logging_config.configure_logging(paths)
    assert sys.excepthook is process_hook
    error = ValueError("synthetic")
    try:
        raise error
    except ValueError as caught:
        process_hook(ValueError, caught, caught.__traceback__)
    _flush()

    assert len(process_calls) == 1
    assert process_calls[0][2] is not None
    text = paths.log_file.read_text(encoding="utf-8")
    assert text.count("unhandled.process exception_type=ValueError") == 1
    assert "Traceback (most recent call last):" in text
    assert "ValueError: synthetic" in text


def test_sh_g_3_thread_hook_logs_once_and_delegates_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    thread_calls: list[object] = []
    monkeypatch.setattr(
        threading,
        "excepthook",
        lambda args: thread_calls.append(args),
    )
    paths = AppPaths.from_root(tmp_path / "app")
    logging_config.configure_logging(paths)
    thread_hook = threading.excepthook
    logging_config.configure_logging(paths)
    assert threading.excepthook is thread_hook
    try:
        raise RuntimeError("thread-synthetic")
    except RuntimeError as caught:
        thread_args = SimpleNamespace(
            exc_type=RuntimeError,
            exc_value=caught,
            exc_traceback=caught.__traceback__,
            thread=threading.current_thread(),
        )
        thread_hook(thread_args)
    _flush()

    assert thread_calls == [thread_args]
    assert thread_args.exc_traceback is not None
    text = paths.log_file.read_text(encoding="utf-8")
    assert text.count("unhandled.thread exception_type=RuntimeError") == 1
    assert "Traceback (most recent call last):" in text
    assert "RuntimeError: thread-synthetic" in text


def test_sh_g_3_later_write_failure_does_not_escape_or_change_shutdown_truth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app")
    logging_config.configure_logging(paths)
    handler = logging_config._handler
    assert handler is not None
    truth = {"complete": True}

    def fail_rollover(record: logging.LogRecord) -> bool:
        del record
        raise OSError("synthetic log failure")

    monkeypatch.setattr(handler, "shouldRollover", fail_rollover)

    logging.getLogger("namisync").info("diagnostic.write-failure")
    logging_config.shutdown_logging()

    assert truth == {"complete": True}
    assert logging_config._handler is None


def test_post_shutdown_cleanup_failure_reaches_the_owned_log(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app")
    logging_config.configure_logging(paths)
    logging_config.shutdown_logging()

    logging_config.record_late_cleanup_failure(
        paths.log_file,
        "startup.mutex_cleanup_failed",
        RuntimeError("native handle detail is not retained"),
    )

    text = paths.log_file.read_text(encoding="utf-8")
    assert "startup.mutex_cleanup_failed exception_type=RuntimeError" in text
    assert "native handle detail is not retained" not in text


def test_post_shutdown_diagnostic_io_failure_cannot_escape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app")
    paths.ensure_directories()
    monkeypatch.setattr(
        logging_config,
        "_OwnedRotatingFileHandler",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic late-open failure")
        ),
    )

    logging_config.record_late_cleanup_failure(
        paths.log_file,
        "startup.mutex_cleanup_failed",
        RuntimeError("mutex release failed"),
    )


def test_configuration_for_another_root_is_refused(tmp_path: Path) -> None:
    logging_config.configure_logging(AppPaths.from_root(tmp_path / "first"))

    with pytest.raises(RuntimeError, match="another root"):
        logging_config.configure_logging(AppPaths.from_root(tmp_path / "second"))


def test_unusable_log_destination_is_an_actionable_startup_failure(
    tmp_path: Path,
) -> None:
    root = tmp_path / "blocked"
    root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(RuntimeError, match="data and log directories"):
        logging_config.configure_logging(AppPaths.from_root(root))


def test_normal_shutdown_records_exit_restores_hooks_and_closes_logging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app")
    original_sys_hook = sys.excepthook
    original_thread_hook = threading.excepthook
    shutdown_calls: list[None] = []

    def shutdown() -> None:
        shutdown_calls.append(None)
        assert logging_config._handler is not None
        logging_config._handler.flush()

    monkeypatch.setattr(logging_config.logging, "shutdown", shutdown)
    logging_config.configure_logging(paths)

    logging_config.shutdown_logging()

    assert shutdown_calls == [None]
    assert logging_config._handler is None
    assert sys.excepthook is original_sys_hook
    assert threading.excepthook is original_thread_hook
    assert "shutdown.complete" in paths.log_file.read_text(encoding="utf-8")


def test_import_and_configuration_load_no_webview_module(tmp_path: Path) -> None:
    root = tmp_path / "child-app"
    script = """
import json
import sys
from namisync.interfaces.web.paths import AppPaths
from namisync.interfaces.web.logging_config import configure_logging
configure_logging(AppPaths.from_root(sys.argv[1]))
print(json.dumps(sorted(
    name for name in sys.modules
    if name == "webview" or name.startswith("webview.")
)))
"""

    completed = subprocess.run(
        [sys.executable, "-c", script, str(root)],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == []
    assert completed.stderr == ""
    assert (root / "logs" / "namisync.log").is_file()
