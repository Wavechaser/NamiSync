"""Bounded GUI logging contract tests."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import threading
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


def test_logging_is_eager_shared_bounded_and_idempotent(tmp_path: Path) -> None:
    paths = AppPaths.from_root(tmp_path / "app")
    root = logging.getLogger()
    root_state = (tuple(root.handlers), root.level, root.propagate)
    prior_sys_hook = sys.excepthook
    prior_thread_hook = threading.excepthook

    first = logging_config.configure_logging(paths)
    handler = logging_config._handler
    process_wrapper = sys.excepthook
    thread_wrapper = threading.excepthook
    second = logging_config.configure_logging(paths)

    assert first == second == paths.log_file.resolve()
    assert paths.log_file.is_file()
    assert handler is not None
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
        assert logger.handlers.count(handler) == 1
    assert (tuple(root.handlers), root.level, root.propagate) == root_state
    assert sys.excepthook is not prior_sys_hook
    assert threading.excepthook is not prior_thread_hook
    assert sys.excepthook is process_wrapper
    assert threading.excepthook is thread_wrapper


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


def test_rotation_and_unicode_fallback_are_emitted_without_internal_error(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app")
    logging_config.configure_logging(paths)
    logger = logging.getLogger("namisync.test")

    logger.info("snowman=\N{SNOWMAN}")
    logger.info("surrogate=\udcff")
    logger.info("a" * (3 * 1024 * 1024))
    logger.info("b" * (3 * 1024 * 1024))
    _flush()

    assert (paths.logs / "namisync.log.1").is_file()
    payload = b"".join(path.read_bytes() for path in paths.logs.iterdir())
    decoded = payload.decode("utf-8")
    assert "snowman=\N{SNOWMAN}" in decoded
    assert r"surrogate=\udcff" in decoded


def test_process_and_thread_hooks_log_once_and_delegate_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process_calls: list[tuple[object, ...]] = []
    thread_calls: list[object] = []
    monkeypatch.setattr(sys, "excepthook", lambda *args: process_calls.append(args))
    monkeypatch.setattr(
        threading,
        "excepthook",
        lambda args: thread_calls.append(args),
    )
    paths = AppPaths.from_root(tmp_path / "app")
    logging_config.configure_logging(paths)
    process_hook = sys.excepthook
    thread_hook = threading.excepthook
    logging_config.configure_logging(paths)
    assert sys.excepthook is process_hook
    assert threading.excepthook is thread_hook
    error = ValueError("synthetic")

    process_hook(ValueError, error, None)
    thread_args = SimpleNamespace(
        exc_type=RuntimeError,
        exc_value=RuntimeError("thread-synthetic"),
        exc_traceback=None,
        thread=None,
    )
    thread_hook(thread_args)
    _flush()

    assert len(process_calls) == 1
    assert thread_calls == [thread_args]
    text = paths.log_file.read_text(encoding="utf-8")
    assert text.count("unhandled.process exception_type=ValueError") == 1
    assert text.count("unhandled.thread exception_type=RuntimeError") == 1


def test_later_write_failure_cannot_change_shutdown_truth(
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
