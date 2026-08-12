"""Product desktop host startup-order and refusal tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import namisync.interfaces.web.host as host
from namisync.interfaces.web.host import (
    DesktopInstanceAdmission,
    DesktopInstanceIdentity,
    DesktopInstanceLease,
    run_desktop,
)
from namisync.interfaces.web.paths import AppPaths


class _Hook:
    def __init__(self) -> None:
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def emit(self) -> None:
        for handler in tuple(self.handlers):
            handler()


class _Window:
    def __init__(self) -> None:
        self.real_url = "http://127.0.0.1:41700/assets/index.html"
        self.events = SimpleNamespace(loaded=_Hook())
        self.destroy_count = 0

    def destroy(self) -> None:
        self.destroy_count += 1


class _Webview:
    def __init__(self, order: list[object]) -> None:
        self.order = order
        self.window = _Window()

    def create_window(self, title: str, url: str, *, js_api: object):
        self.order.append(("create_window", title, url, js_api))
        return self.window


class _Document:
    def __init__(self) -> None:
        self.is_attached = False
        self.attachment_error: str | None = None


class _Service:
    def __init__(
        self,
        order: list[object],
        *,
        state: str = "ready",
        close_error: Exception | None = None,
    ) -> None:
        self.order = order
        self.state = state
        self.close_error = close_error

    def validate_database_contracts(self):
        self.order.append("validate_databases")
        return SimpleNamespace(
            state=self.state,
            reason="history-contract" if self.state == "refused" else None,
            reset_direction=(
                "Reset both database files together."
                if self.state == "refused"
                else None
            ),
        )

    def initialize_database_contracts(self):
        self.order.append("initialize_databases")
        self.state = "ready"
        return SimpleNamespace(state="ready", reason=None, reset_direction=None)

    def close(self):
        self.order.append("service.close")
        if self.close_error is not None:
            raise self.close_error
        return SimpleNamespace(complete=True, unfinished=(), custody_released=True)


class _LeaseNative:
    def __init__(
        self,
        order: list[object],
        error: Exception | None = None,
    ) -> None:
        self.order = order
        self.error = error

    def close_handle(self, handle: object) -> None:
        self.order.append(("lease.close", handle))
        if self.error is not None:
            raise self.error


def _identity() -> DesktopInstanceIdentity:
    return DesktopInstanceIdentity(
        r"Local\NamiSync.Test.Host",
        "NamiSync Test Host",
    )


def _primary(
    order: list[object],
    lease_error: Exception | None = None,
) -> DesktopInstanceAdmission:
    lease = DesktopInstanceLease("owned", _LeaseNative(order, lease_error))
    return DesktopInstanceAdmission(lease, False, None)


def _patch_primary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    database_state: str = "ready",
    configure_security=None,
    start=None,
    close_error: Exception | None = None,
    lease_error: Exception | None = None,
) -> tuple[AppPaths, list[object], _Webview, _Document, list[str]]:
    paths = AppPaths.from_root(tmp_path / "app")
    order: list[object] = []
    reports: list[str] = []
    webview = _Webview(order)
    document = _Document()
    service = _Service(
        order,
        state=database_state,
        close_error=close_error,
    )
    monkeypatch.setattr(
        host,
        "acquire_desktop_instance",
        lambda identity, native=None: order.append(("acquire", identity, native))
        or _primary(order, lease_error),
    )
    monkeypatch.setattr(
        host,
        "_configure_logging",
        lambda actual: order.append(("configure_logging", actual)),
    )
    monkeypatch.setattr(
        host,
        "_load_webview",
        lambda: order.append("import_webview") or webview,
    )
    monkeypatch.setattr(
        host,
        "_log_startup_dependencies",
        lambda: order.append("log_dependencies"),
    )
    monkeypatch.setattr(
        host,
        "_prepare_webview_host",
        lambda actual: order.append(("prepare_webview", actual)),
    )
    monkeypatch.setattr(
        host,
        "_create_service",
        lambda actual: order.append(("create_service", actual)) or service,
    )
    monkeypatch.setattr(
        host,
        "_pending_document",
        lambda: order.append("pending_document") or document,
    )
    dispatcher = object()
    monkeypatch.setattr(
        host,
        "_closed_dispatcher",
        lambda actual: order.append(("closed_dispatcher", actual)) or dispatcher,
    )
    monkeypatch.setattr(
        host,
        "_packaged_index_path",
        lambda: order.append("packaged_index") or "installed/assets/index.html",
    )

    def default_security(window, url, actual_document, renderer_callback):
        order.append(("configure_security", window, url, actual_document))
        actual_document.is_attached = True
        renderer_callback("150.0.0.0")

    monkeypatch.setattr(
        host,
        "_configure_window_security",
        default_security if configure_security is None else configure_security,
    )
    monkeypatch.setattr(
        host,
        "_bind_document_origin",
        lambda actual, url: order.append(("bind_origin", actual, url)),
    )
    monkeypatch.setattr(
        host,
        "_log_startup_renderer",
        lambda value: order.append(("renderer", value)),
    )

    def default_start(
        actual_webview,
        *,
        on_initialized,
        storage_path,
    ) -> None:
        order.append(("start", actual_webview, storage_path))
        on_initialized()

    monkeypatch.setattr(
        host,
        "_start_webview",
        default_start if start is None else start,
    )
    monkeypatch.setattr(
        host,
        "_shutdown_logging",
        lambda: order.append("shutdown_logging"),
    )
    monkeypatch.setattr(
        host,
        "_log_cleanup_failure",
        lambda event, error, **options: order.append(
            (
                "cleanup_failure",
                event,
                type(error).__name__,
                options.get("log_path"),
            )
        ),
    )
    return paths, order, webview, document, reports


def test_host_prepares_before_create_and_starts_only_edge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, order, webview, document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
        database_state="fresh",
    )
    identity = _identity()

    result = run_desktop(paths, identity, startup_error=reports.append)

    assert result == 0
    assert reports == []
    assert document.is_attached
    labels = [entry[0] if isinstance(entry, tuple) else entry for entry in order]
    assert labels == [
        "acquire",
        "configure_logging",
        "import_webview",
        "log_dependencies",
        "prepare_webview",
        "create_service",
        "validate_databases",
        "initialize_databases",
        "pending_document",
        "closed_dispatcher",
        "packaged_index",
        "create_window",
        "start",
        "bind_origin",
        "configure_security",
        "renderer",
        "service.close",
        "shutdown_logging",
        "lease.close",
    ]
    created = next(item for item in order if isinstance(item, tuple) and item[0] == "create_window")
    assert created[1] == identity.window_title
    assert created[2] == "installed/assets/index.html"
    started = next(item for item in order if isinstance(item, tuple) and item[0] == "start")
    assert started[1] is webview
    assert started[2] == str(paths.webview2)


def test_desktop_host_preserves_the_service_boundary() -> None:
    source = Path(host.__file__).read_text(encoding="utf-8")

    assert "namisync.core" not in source
    assert "namisync.modules" not in source
    assert "namisync.db" not in source
    assert "NamiSyncService(" in source


def test_losing_instance_exits_before_logging_or_webview_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = AppPaths.from_root(tmp_path / "not-created")
    reports: list[str] = []
    monkeypatch.setattr(
        host,
        "acquire_desktop_instance",
        lambda identity, native=None: DesktopInstanceAdmission(
            None,
            False,
            "Existing window is still starting.",
        ),
    )
    monkeypatch.setattr(
        host,
        "_configure_logging",
        lambda _paths: pytest.fail("loser configured logging"),
    )
    monkeypatch.setattr(
        host,
        "_load_webview",
        lambda: pytest.fail("loser imported webview"),
    )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 0
    assert reports == ["Existing window is still starting."]
    assert not paths.root.exists()


def test_database_refusal_finalizes_before_visible_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, order, _webview, _document, _reports = _patch_primary(
        monkeypatch,
        tmp_path,
        database_state="refused",
    )

    def report(message: str) -> None:
        order.append(("report", message))

    result = run_desktop(paths, _identity(), startup_error=report)

    assert result == 1
    labels = [entry[0] if isinstance(entry, tuple) else entry for entry in order]
    assert "create_window" not in labels
    assert labels[-4:] == [
        "service.close",
        "shutdown_logging",
        "lease.close",
        "report",
    ]
    assert "history-contract" in order[-1][1]
    assert "both database files together" in order[-1][1]


def test_initialized_refusal_aborts_without_destroy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_security(*_args) -> None:
        raise RuntimeError("origin was unavailable")

    paths, _order, webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
        configure_security=fail_security,
    )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 1
    assert webview.window.destroy_count == 0
    assert reports == ["origin was unavailable"]


def test_guard_or_loaded_refusal_destroys_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed_attachment(window, url, document, renderer_callback) -> None:
        del window, url, renderer_callback
        document.attachment_error = "native event subscription failed"

    def start(webview, *, on_initialized, storage_path) -> None:
        del storage_path
        on_initialized()
        webview.window.events.loaded.emit()
        webview.window.events.loaded.emit()

    paths, _order, webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
        configure_security=failed_attachment,
        start=start,
    )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 1
    assert webview.window.destroy_count == 1
    assert reports == [
        "WebView2 security guards could not attach: "
        "native event subscription failed"
    ]


def test_original_startup_failure_survives_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_security(*_args) -> None:
        raise RuntimeError("original startup failure")

    paths, _order, _webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
        configure_security=fail_security,
        close_error=RuntimeError("secondary cleanup failure"),
    )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 1
    assert reports == ["original startup failure"]


@pytest.mark.parametrize("cleanup", ("logging", "mutex"))
def test_original_failure_survives_and_records_late_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cleanup: str,
) -> None:
    def fail_security(*_args) -> None:
        raise RuntimeError("original startup failure")

    paths, order, _webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
        configure_security=fail_security,
        lease_error=(
            RuntimeError("mutex release failed")
            if cleanup == "mutex"
            else None
        ),
    )
    if cleanup == "logging":
        monkeypatch.setattr(
            host,
            "_shutdown_logging",
            lambda: (_ for _ in ()).throw(
                RuntimeError("logging shutdown failed")
            ),
        )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 1
    assert reports == ["original startup failure"]
    event = (
        "startup.logging_cleanup_failed"
        if cleanup == "logging"
        else "startup.mutex_cleanup_failed"
    )
    assert (
        "cleanup_failure",
        event,
        "RuntimeError",
        paths.log_file,
    ) in order


def test_loaded_watchdog_records_destroy_failure_without_raising(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed_attachment(window, url, document, renderer_callback) -> None:
        del window, url, renderer_callback
        document.attachment_error = "guard attachment failed"

    def start(webview, *, on_initialized, storage_path) -> None:
        del storage_path
        on_initialized()
        webview.window.destroy = lambda: (_ for _ in ()).throw(
            RuntimeError("destroy failed")
        )
        webview.window.events.loaded.emit()

    paths, order, _webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
        configure_security=failed_attachment,
        start=start,
    )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 1
    assert reports == [
        "WebView2 security guards could not attach: guard attachment failed"
    ]
    assert (
        "cleanup_failure",
        "startup.window_destroy_failed",
        "RuntimeError",
        None,
    ) in order
