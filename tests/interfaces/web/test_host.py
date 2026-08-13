"""Product desktop host startup-order and refusal tests."""

from __future__ import annotations

import ast
from pathlib import Path
from threading import Event, Lock, Thread, current_thread
from time import monotonic
from types import SimpleNamespace

import pytest

import namisync.interfaces.web.host as host
from namisync.interfaces.web.commands import PickerUnavailableError
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

    def __isub__(self, handler):
        self.handlers.remove(handler)
        return self

    def emit(self) -> list[object]:
        return [handler() for handler in tuple(self.handlers)]


class _Window:
    def __init__(self) -> None:
        self.real_url = "http://127.0.0.1:41700/assets/index.html"
        self.events = SimpleNamespace(closing=_Hook(), loaded=_Hook())
        self.destroy_count = 0
        self.destroyed = Event()
        self.exposed_functions: tuple[object, ...] = ()

    def expose(self, *functions: object) -> None:
        self.exposed_functions = functions

    def destroy(self) -> None:
        self.destroy_count += 1
        self.destroyed.set()


class _Webview:
    def __init__(self, order: list[object]) -> None:
        self.order = order
        self.window = _Window()

    def create_window(
        self,
        title: str,
        url: str,
        *,
        js_api: object,
        background_color: str,
        transparent: bool,
    ):
        self.order.append(
            (
                "create_window",
                title,
                url,
                js_api,
                background_color,
                transparent,
            )
        )
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
    path_lease = SimpleNamespace(
        bind_databases=lambda: order.append("path_lease.bind_databases"),
        close=lambda: order.append("path_lease.close"),
    )
    monkeypatch.setattr(
        AppPaths,
        "acquire_lease",
        lambda self: order.append("path_lease.acquire") or path_lease,
    )
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
    slots = SimpleNamespace()
    registry = SimpleNamespace(
        begin_close=lambda: order.append("registry.begin_close"),
        unsubscribe_all=lambda: order.append("registry.unsubscribe_all"),
    )
    commands = SimpleNamespace()
    dispatcher = SimpleNamespace(
        begin_close=lambda: order.append("reject_dispatch"),
        wait_for_handlers=lambda: order.append("wait_handlers"),
        dispatch=lambda _body: None,
    )

    class Picker:
        def __init__(self, actual_webview: object) -> None:
            order.append(("native_picker", actual_webview))

        def bind(self, window: object) -> None:
            order.append(("bind_picker", window))

    monkeypatch.setattr(
        host,
        "_folder_slots",
        lambda: order.append(("folder_slots", slots)) or slots,
    )
    monkeypatch.setattr(
        host,
        "_task_registry",
        lambda actual: order.append(("task_registry", actual, registry))
        or registry,
    )
    monkeypatch.setattr(host, "_NativeFolderPicker", Picker)
    monkeypatch.setattr(
        host,
        "_production_commands",
        lambda **dependencies: order.append(
            ("production_commands", dependencies, commands)
        )
        or commands,
    )
    monkeypatch.setattr(
        host,
        "_bridge_dispatcher",
        lambda actual_document, actual_commands: order.append(
            (
                "bridge_dispatcher",
                actual_document,
                actual_commands,
                dispatcher,
            )
        )
        or dispatcher,
    )
    monkeypatch.setattr(
        host,
        "_packaged_index_path",
        lambda: order.append("packaged_index") or "installed/assets/index.html",
    )
    monkeypatch.setattr(
        host,
        "_opaque_window_background",
        lambda: order.append("opaque_background") or "#F3F3F3",
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

    class Appearance:
        def close(self) -> None:
            order.append("appearance.close")

    monkeypatch.setattr(
        host,
        "_configure_window_appearance",
        lambda window: order.append(("configure_appearance", window))
        or Appearance(),
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
        "_render_close_status",
        lambda _window, phase: order.append(("close_status", phase.value)),
    )
    monkeypatch.setattr(
        host,
        "_show_retry_close_prompt",
        lambda _title: pytest.fail("unexpected close retry prompt"),
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
        "path_lease.acquire",
        "configure_logging",
        "import_webview",
        "log_dependencies",
        "prepare_webview",
        "create_service",
        "validate_databases",
        "initialize_databases",
        "path_lease.bind_databases",
        "validate_databases",
        "task_registry",
        "pending_document",
        "folder_slots",
        "native_picker",
        "production_commands",
        "bridge_dispatcher",
        "packaged_index",
        "opaque_background",
        "create_window",
        "bind_picker",
        "start",
        "bind_origin",
        "configure_security",
        "renderer",
        "configure_appearance",
        "reject_dispatch",
        "registry.begin_close",
        "wait_handlers",
        "registry.unsubscribe_all",
        "service.close",
        "appearance.close",
        "shutdown_logging",
        "path_lease.close",
        "lease.close",
    ]
    created = next(item for item in order if isinstance(item, tuple) and item[0] == "create_window")
    assert created[1] == identity.window_title
    assert created[2] == "installed/assets/index.html"
    slots_entry = next(item for item in order if item[0] == "folder_slots")
    commands_entry = next(
        item for item in order if item[0] == "production_commands"
    )
    bridge_entry = next(
        item for item in order if item[0] == "bridge_dispatcher"
    )
    assert commands_entry[1]["slots"] is slots_entry[1]
    assert commands_entry[1]["registry"] is next(
        item for item in order if item[0] == "task_registry"
    )[2]
    assert bridge_entry[2] is commands_entry[2]
    assert created[3] is None
    assert created[4] == "#F3F3F3"
    assert created[5] is False
    assert len(webview.window.exposed_functions) == 1
    exposed_dispatch = webview.window.exposed_functions[0]
    assert exposed_dispatch.__name__ == "dispatch"
    started = next(item for item in order if isinstance(item, tuple) and item[0] == "start")
    assert started[1] is webview
    assert started[2] == str(paths.webview2)


def test_br_g_32_native_folder_picker_is_late_bound_and_uses_public_api() -> None:
    folder_kind = object()
    calls: list[tuple[object, ...]] = []
    selected: object = (r"C:\private\selected",)

    def create_file_dialog(kind: object, *, allow_multiple: bool) -> object:
        calls.append((kind, allow_multiple))
        return selected

    window = SimpleNamespace(create_file_dialog=create_file_dialog)
    webview = SimpleNamespace(FileDialog=SimpleNamespace(FOLDER=folder_kind))
    picker = host._NativeFolderPicker(webview)

    with pytest.raises(RuntimeError, match="not bound"):
        picker()

    picker.bind(window)
    assert picker() == (r"C:\private\selected",)
    assert calls == [(folder_kind, False)]

    selected = None
    assert picker() is None
    assert calls == [(folder_kind, False), (folder_kind, False)]
    with pytest.raises(RuntimeError, match="already bound"):
        picker.bind(window)

    source = Path(host.__file__).read_text(encoding="utf-8")
    assert "webview.platforms" not in source
    assert "webview.platforms.edgechromium" not in source


def test_br_g_32_native_folder_picker_is_nonblocking_single_flight() -> None:
    entered = Event()
    release = Event()
    active_lock = Lock()
    active = 0
    maximum_active = 0
    calls = 0

    def create_file_dialog(kind: object, *, allow_multiple: bool):
        nonlocal active, maximum_active, calls
        assert kind is folder_kind
        assert allow_multiple is False
        with active_lock:
            calls += 1
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            entered.set()
            if calls == 1:
                assert release.wait(2.0)
            return (r"C:\private\selected",)
        finally:
            with active_lock:
                active -= 1

    class Slots:
        def store(self, path: str, *, purpose: str) -> tuple[str, str]:
            assert path == r"C:\private\selected"
            assert purpose == "source"
            return "slot-" + "1" * 32, "Selected"

        def resolve_pair(self, source_id: str, target_id: str):
            raise AssertionError((source_id, target_id))

    folder_kind = object()
    webview = SimpleNamespace(FileDialog=SimpleNamespace(FOLDER=folder_kind))
    picker = host._NativeFolderPicker(webview)
    picker.bind(SimpleNamespace(create_file_dialog=create_file_dialog))
    commands = host._production_commands(
        picker=picker,
        slots=Slots(),
        registry=host._task_registry(_Service([])),
    )
    first: list[object] = []
    worker = Thread(
        target=lambda: first.append(
            commands["pick_folder"].invoke({"purpose": "source"})
        )
    )
    worker.start()
    assert entered.wait(1.0)

    with pytest.raises(PickerUnavailableError):
        commands["pick_folder"].invoke({"purpose": "source"})
    assert maximum_active == 1

    release.set()
    worker.join(2.0)
    assert not worker.is_alive()
    assert first == [{"id": "slot-" + "1" * 32, "display": "Selected"}]

    assert commands["pick_folder"].invoke({"purpose": "source"}) == {
        "id": "slot-" + "1" * 32,
        "display": "Selected",
    }
    assert calls == 2
    assert maximum_active == 1


@pytest.mark.parametrize(
    "outcome",
    [None, SystemExit("private native termination")],
)
def test_br_g_32_native_folder_picker_releases_single_flight_on_every_exit(
    outcome: object,
) -> None:
    calls = 0
    folder_kind = object()

    def create_file_dialog(kind: object, *, allow_multiple: bool):
        nonlocal calls
        assert kind is folder_kind
        assert allow_multiple is False
        calls += 1
        if calls == 1:
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        return (r"C:\private\later",)

    picker = host._NativeFolderPicker(
        SimpleNamespace(FileDialog=SimpleNamespace(FOLDER=folder_kind))
    )
    picker.bind(SimpleNamespace(create_file_dialog=create_file_dialog))

    if isinstance(outcome, BaseException):
        with pytest.raises(type(outcome)):
            picker()
    else:
        assert picker() is None
    assert picker() == (r"C:\private\later",)
    assert calls == 2


def test_br_g_32_host_exposes_only_dispatch_through_function_table() -> None:
    document = SimpleNamespace(require_trusted=lambda: None)
    slots = host._folder_slots()
    commands = host._production_commands(
        picker=lambda: None,
        slots=slots,
        registry=host._task_registry(_Service([])),
    )
    dispatcher = host._bridge_dispatcher(document, commands)

    assert tuple(commands) == (
        "pick_folder",
        "start_plan",
        "next_events",
        "release_terminal_session",
        "close_task",
    )
    assert tuple(dispatcher._commands) == (
        "pick_folder",
        "start_plan",
        "next_events",
        "release_terminal_session",
        "close_task",
    )
    window = SimpleNamespace(
        _js_api=None,
        _functions={},
        expose=lambda *functions: window._functions.update(
            {function.__name__: function for function in functions}
        ),
    )

    host._expose_bridge_api(window, dispatcher)

    assert window._js_api is None
    assert tuple(window._functions) == ("dispatch",)
    assert window._functions["dispatch"]("{}") == dispatcher.dispatch("{}")
    assert set(window._functions) == {"dispatch"}


def test_host_accepts_only_a_construction_injected_local_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, order, _webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
    )
    index = tmp_path / "headed-probe.html"
    index.write_text("<!doctype html>", encoding="utf-8")
    monkeypatch.setattr(
        host,
        "_packaged_index_path",
        lambda: pytest.fail("injected host resolved the packaged index"),
    )

    result = run_desktop(
        paths,
        _identity(),
        startup_error=reports.append,
        index_path=index,
    )

    assert result == 0
    assert reports == []
    created = next(
        item
        for item in order
        if isinstance(item, tuple) and item[0] == "create_window"
    )
    assert created[2] == str(index.resolve())


def test_host_rejects_an_invalid_construction_index_before_window_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, order, _webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
    )

    result = run_desktop(
        paths,
        _identity(),
        startup_error=reports.append,
        index_path="relative-headed-probe.html",
    )

    assert result == 1
    assert len(reports) == 1
    assert "absolute local path" in reports[0]
    labels = [entry[0] if isinstance(entry, tuple) else entry for entry in order]
    assert "create_window" not in labels
    assert "start" not in labels


def test_br_g_19_desktop_host_preserves_the_interface_boundary() -> None:
    source = Path(host.__file__).read_text(encoding="utf-8")

    assert "namisync.core" not in source
    assert "namisync.modules" not in source
    assert "namisync.db" not in source
    assert "NamiSyncService(" in source

    package_root = Path(host.__file__).parents[2]
    interfaces_root = package_root / "interfaces"
    pathing_tree = ast.parse(
        (package_root / "core" / "pathing.py").read_text(encoding="utf-8")
    )
    path_helpers = {
        node.name
        for node in pathing_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    forbidden_calls: list[tuple[str, int, str]] = []
    for interface_source in interfaces_root.rglob("*.py"):
        tree = ast.parse(
            interface_source.read_text(encoding="utf-8"),
            filename=str(interface_source),
        )
        imported_aliases = {
            alias.asname or alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "namisync.core.pathing"
            for alias in node.names
            if alias.name in path_helpers
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = node.func
            name = (
                called.id
                if isinstance(called, ast.Name)
                else called.attr
                if isinstance(called, ast.Attribute)
                else None
            )
            if name in path_helpers or name in imported_aliases:
                forbidden_calls.append(
                    (
                        str(interface_source.relative_to(package_root)),
                        node.lineno,
                        name,
                    )
                )

    assert forbidden_calls == []


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
    assert labels[-5:] == [
        "service.close",
        "shutdown_logging",
        "path_lease.close",
        "lease.close",
        "report",
    ]
    assert "history-contract" in order[-1][1]
    assert "both database files together" in order[-1][1]


def test_startup_finalizer_quiesces_registry_before_service_close() -> None:
    order: list[str] = []
    dispatcher = SimpleNamespace(
        begin_close=lambda: order.append("reject"),
        wait_for_handlers=lambda: order.append("wait"),
    )
    registry = SimpleNamespace(
        begin_close=lambda: order.append("wake"),
        unsubscribe_all=lambda: order.append("unsubscribe"),
    )
    service = _ControllerService(order, [_shutdown_view(complete=True)])

    failure = host._finalize_primary(
        service,
        dispatcher=dispatcher,
        registry=registry,
        service_shutdown_complete=False,
        logging_configured=False,
        log_path=None,
        lease=None,
    )

    assert failure is None
    assert order == ["reject", "wake", "wait", "unsubscribe", "service.close"]


def test_startup_finalizer_preserves_quiesce_error_without_unsafe_service_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    first = RuntimeError("first cleanup failure")

    def fail_wake() -> None:
        order.append("wake")
        raise first

    dispatcher = SimpleNamespace(
        begin_close=lambda: order.append("reject"),
        wait_for_handlers=lambda: order.append("wait"),
    )
    registry = SimpleNamespace(
        begin_close=fail_wake,
        unsubscribe_all=lambda: order.append("unsubscribe"),
    )
    service = _ControllerService(
        order,
        [RuntimeError("later service failure")],
    )
    logged: list[str] = []
    monkeypatch.setattr(
        host,
        "_log_cleanup_failure",
        lambda event, _error, **_options: logged.append(event),
    )

    path_lease = SimpleNamespace(close=lambda: order.append("path.close"))
    native = _LeaseNative(order)
    instance_lease = DesktopInstanceLease("owned", native)
    monkeypatch.setattr(
        host,
        "_shutdown_logging",
        lambda: order.append("logging.close"),
    )

    failure = host._finalize_primary(
        service,
        dispatcher=dispatcher,
        registry=registry,
        service_shutdown_complete=False,
        logging_configured=True,
        log_path=Path("NamiSync.log"),
        lease=instance_lease,
        path_lease=path_lease,
    )

    assert failure is first
    assert order == ["reject", "wake"]
    assert logged == ["startup.registry_wake_failed"]


@pytest.mark.parametrize(
    "first_kind",
    ["incomplete", "exception"],
)
def test_startup_finalizer_retains_every_owner_until_complete_retry(
    monkeypatch: pytest.MonkeyPatch,
    first_kind: str,
) -> None:
    order: list[object] = []
    logged: list[str] = []
    dispatcher = SimpleNamespace(
        begin_close=lambda: order.append("reject"),
        wait_for_handlers=lambda: order.append("wait"),
    )
    registry = SimpleNamespace(
        begin_close=lambda: order.append("wake"),
        unsubscribe_all=lambda: order.append("unsubscribe"),
    )
    first_outcome = (
        _shutdown_view(complete=False)
        if first_kind == "incomplete"
        else RuntimeError("injected close failure")
    )
    service = _ControllerService(
        order,
        [first_outcome, _shutdown_view(complete=True)],
    )
    path_lease = SimpleNamespace(close=lambda: order.append("path.close"))
    instance_lease = DesktopInstanceLease("owned", _LeaseNative(order))
    monkeypatch.setattr(
        host,
        "_shutdown_logging",
        lambda: order.append("logging.close"),
    )
    monkeypatch.setattr(
        host,
        "_log_cleanup_failure",
        lambda event, _error, **_options: logged.append(event),
    )
    options = {
        "dispatcher": dispatcher,
        "registry": registry,
        "service_shutdown_complete": False,
        "logging_configured": True,
        "log_path": Path("NamiSync.log"),
        "lease": instance_lease,
        "path_lease": path_lease,
        "close_presentation": lambda: order.append("presentation.close"),
    }

    first_failure = host._finalize_primary(service, **options)

    assert first_failure is not None
    assert order == ["reject", "wake", "wait", "unsubscribe", "service.close"]

    retry_failure = host._finalize_primary(service, **options)

    assert retry_failure is None
    assert order == [
        "reject",
        "wake",
        "wait",
        "unsubscribe",
        "service.close",
        "reject",
        "wake",
        "wait",
        "unsubscribe",
        "service.close",
        "presentation.close",
        "logging.close",
        "path.close",
        ("lease.close", "owned"),
    ]
    assert logged == (
        ["startup.service_cleanup_failed"]
        if first_kind == "exception"
        else []
    )


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


def test_appearance_configuration_failure_refuses_startup_after_security(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    paths, order, _webview, document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
    )
    monkeypatch.setattr(
        host,
        "_configure_window_appearance",
        lambda _window: (_ for _ in ()).throw(
            RuntimeError("injected material failure")
        ),
    )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 1
    assert reports == ["injected material failure"]
    assert document.is_attached
    assert "service.close" in order
    assert "appearance.configuration_failed" in caplog.text


def test_appearance_cleanup_failure_is_nonfatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    paths, order, _webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
    )

    class Appearance:
        def close(self) -> None:
            order.append("appearance.close")
            raise RuntimeError("injected unsubscribe failure")

    monkeypatch.setattr(
        host,
        "_configure_window_appearance",
        lambda _window: Appearance(),
    )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 0
    assert reports == []
    assert order.index("service.close") < order.index("appearance.close")
    assert "appearance.cleanup_failed" in caplog.text


def test_unconfirmed_window_material_refuses_startup_before_open_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def start(webview, *, on_initialized, storage_path) -> None:
        del storage_path
        on_initialized()
        webview.window.events.loaded.emit()

    paths, order, webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
        start=start,
    )

    class Appearance:
        startup_failure = RuntimeError(
            "NamiSync could not establish a readable window material"
        )

        def close(self) -> None:
            order.append("appearance.close")

    monkeypatch.setattr(
        host,
        "_configure_window_appearance",
        lambda _window: Appearance(),
    )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 1
    assert reports == ["NamiSync could not establish a readable window material"]
    assert webview.window.destroy_count == 1
    assert order.count("appearance.close") == 1


def test_security_failure_never_attempts_appearance_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_security(*_args) -> None:
        raise RuntimeError("security failure")

    paths, _order, _webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
        configure_security=fail_security,
    )
    configured: list[object] = []
    monkeypatch.setattr(
        host,
        "_configure_window_appearance",
        lambda window: configured.append(window),
    )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 1
    assert reports == ["security failure"]
    assert configured == []


def test_close_hooks_quiesce_tasks_without_retiring_appearance() -> None:
    order: list[str] = []
    dispatcher = SimpleNamespace(
        begin_close=lambda: order.append("reject"),
        wait_for_handlers=lambda: order.append("wait"),
    )
    registry = SimpleNamespace(
        begin_close=lambda: order.append("wake"),
        unsubscribe_all=lambda: order.append("unsubscribe"),
    )

    hooks = host._desktop_close_hooks(dispatcher, registry)
    hooks.reject_dispatch()
    hooks.wake_waiters()
    hooks.wait_for_handlers()
    hooks.unsubscribe_observations()

    assert order == [
        "reject",
        "wake",
        "wait",
        "unsubscribe",
    ]


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
        original_destroy = webview.window.destroy

        def destroy() -> None:
            order.append("destroy")
            original_destroy()

        webview.window.destroy = destroy
        webview.window.events.loaded.emit()
        webview.window.events.loaded.emit()

    paths, order, webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
        configure_security=failed_attachment,
        start=start,
    )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 1
    assert webview.window.destroy_count == 1
    assert order.index("appearance.close") < order.index("destroy")
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


def test_post_logging_startup_failure_is_recorded_once_before_finalization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_after_initialization(
        webview,
        *,
        on_initialized,
        storage_path,
    ) -> None:
        del webview, storage_path
        on_initialized()
        raise RuntimeError("original startup failure")

    paths, order, _webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
        start=fail_after_initialization,
    )
    monkeypatch.setattr(
        host,
        "_log_startup_failure",
        lambda error: order.append(("startup.failed", type(error).__name__)),
    )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 1
    assert reports == ["original startup failure"]
    labels = [entry[0] if isinstance(entry, tuple) else entry for entry in order]
    assert labels.count("startup.failed") == 1
    assert labels.index("startup.failed") < labels.index("service.close")
    assert labels.index("startup.failed") < labels.index("appearance.close")
    assert labels.index("startup.failed") < labels.index("shutdown_logging")
    assert labels.index("startup.failed") < labels.index("path_lease.close")
    assert labels.index("startup.failed") < labels.index("lease.close")


def test_pre_logging_failure_does_not_attempt_startup_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, order, _webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
    )
    monkeypatch.setattr(
        host,
        "_configure_logging",
        lambda _paths: (_ for _ in ()).throw(RuntimeError("logging unavailable")),
    )
    monkeypatch.setattr(
        host,
        "_log_startup_failure",
        lambda _error: pytest.fail("pre-logging failure was logged"),
    )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 1
    assert reports == ["logging unavailable"]
    assert "path_lease.close" in order
    assert any(
        isinstance(entry, tuple) and entry[0] == "lease.close"
        for entry in order
    )


@pytest.mark.parametrize(
    "diagnostic_failure",
    [RuntimeError("diagnostic failure"), KeyboardInterrupt()],
)
def test_startup_diagnostic_failure_cannot_replace_original_or_skip_teardown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    diagnostic_failure: BaseException,
) -> None:
    def fail_after_initialization(
        webview,
        *,
        on_initialized,
        storage_path,
    ) -> None:
        del webview, storage_path
        on_initialized()
        raise RuntimeError("original startup failure")

    paths, order, _webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
        start=fail_after_initialization,
    )
    monkeypatch.setattr(
        host,
        "_log_startup_failure",
        lambda _error: (_ for _ in ()).throw(diagnostic_failure),
    )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 1
    assert reports == ["original startup failure"]
    assert "service.close" in order
    assert "appearance.close" in order
    assert "shutdown_logging" in order
    assert "path_lease.close" in order
    assert any(
        isinstance(entry, tuple) and entry[0] == "lease.close"
        for entry in order
    )


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


def _close_hooks(order: list[str]) -> host._DesktopCloseHooks:
    return host._DesktopCloseHooks(
        reject_dispatch=lambda: order.append("reject"),
        wake_waiters=lambda: order.append("wake"),
        wait_for_handlers=lambda: order.append("wait"),
        unsubscribe_observations=lambda: order.append("unsubscribe"),
    )


class _ControllerWindow:
    def __init__(self, order: list[str]) -> None:
        self.order = order
        self.controller: host._DesktopCloseController | None = None
        self.destroy_count = 0
        self.destroyed = Event()
        self.recursive_close_results: list[bool | None] = []

    def destroy(self) -> None:
        self.order.append("destroy")
        assert self.controller is not None
        result = self.controller._on_closing()
        self.recursive_close_results.append(result)
        if result is False:
            return
        self.destroy_count += 1
        self.destroyed.set()


class _ControllerService:
    def __init__(
        self,
        order: list[str],
        outcomes: list[object],
        *,
        entered: Event | None = None,
        release: Event | None = None,
    ) -> None:
        self.order = order
        self.outcomes = outcomes
        self.entered = entered
        self.release = release
        self.close_threads: list[object] = []
        self.close_count = 0

    def close(self):
        self.order.append("service.close")
        self.close_threads.append(current_thread())
        self.close_count += 1
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            assert self.release.wait(2.0)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _shutdown_view(*, complete: bool):
    return SimpleNamespace(
        complete=complete,
        unfinished=() if complete else ("admitted",),
        custody_released=complete,
    )


def _wait_until(predicate, *, timeout: float = 2.0) -> None:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if predicate():
            return
        Event().wait(0.005)
    raise AssertionError("condition did not become true before timeout")


def test_close_callback_is_nonblocking_and_quiesces_in_exact_order() -> None:
    order: list[str] = []
    entered = Event()
    release = Event()
    window = _ControllerWindow(order)
    service = _ControllerService(
        order,
        [_shutdown_view(complete=True)],
        entered=entered,
        release=release,
    )
    controller = host._DesktopCloseController(
        window,
        service,
        _close_hooks(order),
        window_title="NamiSync Test Close",
        close_appearance=lambda: order.append("appearance.close"),
        render_status=lambda _window, _phase: None,
        retry_prompt=lambda: pytest.fail("healthy close prompted for retry"),
    )
    window.controller = controller
    controller._mark_loaded()

    started = monotonic()
    assert controller._on_closing() is False
    elapsed = monotonic() - started

    assert elapsed < 0.1
    assert entered.wait(1.0)
    assert controller._on_closing() is False
    assert service.close_count == 1
    release.set()
    assert window.destroyed.wait(1.0)
    assert order == [
        "reject",
        "wake",
        "wait",
        "unsubscribe",
        "service.close",
        "appearance.close",
        "destroy",
    ]
    assert service.close_threads[0] is not current_thread()
    assert window.destroy_count == 1
    assert window.recursive_close_results == [None]
    assert controller.service_shutdown_complete


def test_incomplete_close_requires_explicit_retry_and_second_x_does_not_retry() -> None:
    order: list[str] = []
    prompts: list[int] = []
    prompt_lock = Lock()
    window = _ControllerWindow(order)
    service = _ControllerService(
        order,
        [_shutdown_view(complete=False), _shutdown_view(complete=True)],
    )

    def retry_prompt() -> bool:
        with prompt_lock:
            prompts.append(len(prompts) + 1)
            return len(prompts) == 2

    controller = host._DesktopCloseController(
        window,
        service,
        _close_hooks(order),
        window_title="NamiSync Test Close",
        close_appearance=lambda: order.append("appearance.close"),
        render_status=lambda _window, phase: order.append(
            f"status.{phase.value}"
        ),
        retry_prompt=retry_prompt,
    )
    window.controller = controller
    controller._mark_loaded()

    assert controller._on_closing() is False
    _wait_until(
        lambda: service.close_count == 1
        and prompts == [1]
        and not controller._prompt_active
    )
    assert window.destroy_count == 0
    assert not controller.service_shutdown_complete

    assert controller._on_closing() is False
    assert window.destroyed.wait(1.0)

    assert prompts == [1, 2]
    assert service.close_count == 2
    assert window.destroy_count == 1
    assert order.count("service.close") == 2
    first_close = order.index("service.close")
    second_close = order.index("service.close", first_close + 1)
    assert first_close < order.index("status.retryable") < second_close
    assert order.count("appearance.close") == 1
    assert second_close < order.index("appearance.close") < order.index("destroy")


def test_close_exception_uses_the_same_retry_path_without_force_destroy() -> None:
    order: list[str] = []
    prompted = Event()
    allow_retry = Event()
    window = _ControllerWindow(order)
    service = _ControllerService(
        order,
        [RuntimeError("synthetic close failure"), _shutdown_view(complete=True)],
    )

    def retry_prompt() -> bool:
        prompted.set()
        return allow_retry.wait(1.0)

    controller = host._DesktopCloseController(
        window,
        service,
        _close_hooks(order),
        window_title="NamiSync Test Close",
        close_appearance=lambda: order.append("appearance.close"),
        render_status=lambda _window, _phase: None,
        retry_prompt=retry_prompt,
    )
    window.controller = controller
    controller._mark_loaded()

    assert controller._on_closing() is False
    assert prompted.wait(1.0)
    assert window.destroy_count == 0
    assert controller._on_closing() is False
    assert service.close_count == 1

    allow_retry.set()
    assert window.destroyed.wait(1.0)
    assert service.close_count == 2
    assert window.destroy_count == 1
    assert order.count("appearance.close") == 1
    assert order.index("appearance.close") < order.index("destroy")


def test_handler_wait_timeout_keeps_service_open_until_explicit_retry() -> None:
    order: list[str] = []
    prompts: list[int] = []
    waits = 0
    window = _ControllerWindow(order)
    service = _ControllerService(order, [_shutdown_view(complete=True)])

    def wait_for_handlers() -> None:
        nonlocal waits
        waits += 1
        order.append(f"wait.{waits}")
        if waits == 1:
            raise TimeoutError("synthetic admitted handler timeout")

    def retry_prompt() -> bool:
        prompts.append(len(prompts) + 1)
        return len(prompts) == 2

    controller = host._DesktopCloseController(
        window,
        service,
        host._DesktopCloseHooks(
            reject_dispatch=lambda: order.append("reject"),
            wake_waiters=lambda: order.append("wake"),
            wait_for_handlers=wait_for_handlers,
            unsubscribe_observations=lambda: order.append("unsubscribe"),
        ),
        window_title="NamiSync Test Close",
        close_appearance=lambda: order.append("appearance.close"),
        render_status=lambda _window, _phase: None,
        retry_prompt=retry_prompt,
    )
    window.controller = controller
    controller._mark_loaded()

    assert controller._on_closing() is False
    _wait_until(lambda: prompts == [1] and not controller._prompt_active)
    assert service.close_count == 0
    assert "unsubscribe" not in order
    assert window.destroy_count == 0

    assert controller._on_closing() is False
    assert window.destroyed.wait(1.0)
    assert prompts == [1, 2]
    assert service.close_count == 1
    assert order == [
        "reject",
        "wake",
        "wait.1",
        "reject",
        "wake",
        "wait.2",
        "unsubscribe",
        "service.close",
        "appearance.close",
        "destroy",
    ]


def test_observation_unsubscribe_failure_retains_appearance_until_retry() -> None:
    order: list[str] = []
    prompts: list[int] = []
    unsubscribes = 0
    window = _ControllerWindow(order)
    service = _ControllerService(order, [_shutdown_view(complete=True)])

    def unsubscribe() -> None:
        nonlocal unsubscribes
        unsubscribes += 1
        order.append(f"unsubscribe.{unsubscribes}")
        if unsubscribes == 1:
            raise RuntimeError("synthetic observation unsubscribe failure")

    def retry_prompt() -> bool:
        prompts.append(len(prompts) + 1)
        return len(prompts) == 2

    controller = host._DesktopCloseController(
        window,
        service,
        host._DesktopCloseHooks(
            reject_dispatch=lambda: order.append("reject"),
            wake_waiters=lambda: order.append("wake"),
            wait_for_handlers=lambda: order.append("wait"),
            unsubscribe_observations=unsubscribe,
        ),
        window_title="NamiSync Test Close",
        close_appearance=lambda: order.append("appearance.close"),
        render_status=lambda _window, _phase: None,
        retry_prompt=retry_prompt,
    )
    window.controller = controller
    controller._mark_loaded()

    assert controller._on_closing() is False
    _wait_until(lambda: prompts == [1] and not controller._prompt_active)
    assert service.close_count == 0
    assert "appearance.close" not in order
    assert window.destroy_count == 0

    assert controller._on_closing() is False
    assert window.destroyed.wait(1.0)
    assert service.close_count == 1
    assert order.count("appearance.close") == 1
    assert order.index("service.close") < order.index("appearance.close")
    assert order.index("appearance.close") < order.index("destroy")


def test_bridge_rejection_precedes_a_blocked_close_status_render() -> None:
    order: list[str] = []
    rejected = Event()
    render_entered = Event()
    release_render = Event()
    release_service = Event()
    window = _ControllerWindow(order)
    service = _ControllerService(
        order,
        [_shutdown_view(complete=True)],
        release=release_service,
    )
    hooks = host._DesktopCloseHooks(
        reject_dispatch=lambda: (order.append("reject"), rejected.set()),
        wake_waiters=lambda: order.append("wake"),
        wait_for_handlers=lambda: order.append("wait"),
        unsubscribe_observations=lambda: order.append("unsubscribe"),
    )

    def blocked_render(_window: object, _phase: host._ClosePhase) -> None:
        render_entered.set()
        assert release_render.wait(1.0)

    controller = host._DesktopCloseController(
        window,
        service,
        hooks,
        window_title="NamiSync Test Close",
        render_status=blocked_render,
        retry_prompt=lambda: False,
    )
    window.controller = controller
    controller._mark_loaded()

    started = monotonic()
    assert controller._on_closing() is False

    assert monotonic() - started < 0.1
    assert rejected.wait(0.2)
    assert render_entered.wait(0.2)
    _wait_until(lambda: service.close_count == 1)
    assert order[:4] == ["reject", "wake", "wait", "unsubscribe"]
    release_service.set()
    assert window.destroyed.wait(1.0)
    release_render.set()


def test_closing_status_can_render_while_an_admitted_handler_is_still_waiting() -> None:
    order: list[str] = []
    waiting = Event()
    release_wait = Event()
    status_visible = Event()
    window = _ControllerWindow(order)
    service = _ControllerService(order, [_shutdown_view(complete=True)])
    hooks = host._DesktopCloseHooks(
        reject_dispatch=lambda: order.append("reject"),
        wake_waiters=lambda: order.append("wake"),
        wait_for_handlers=lambda: (
            waiting.set(),
            release_wait.wait(1.0),
            order.append("wait"),
        ),
        unsubscribe_observations=lambda: order.append("unsubscribe"),
    )
    controller = host._DesktopCloseController(
        window,
        service,
        hooks,
        window_title="NamiSync Test Close",
        render_status=lambda _window, phase: (
            order.append(f"status.{phase.value}"),
            status_visible.set(),
        ),
        retry_prompt=lambda: False,
    )
    window.controller = controller
    controller._mark_loaded()

    assert controller._on_closing() is False
    assert waiting.wait(1.0)
    assert status_visible.wait(0.2)

    assert service.close_count == 0
    assert order[:2] == ["reject", "wake"]
    release_wait.set()
    assert window.destroyed.wait(1.0)


def test_retry_claim_registers_the_next_attempt_before_releasing_state() -> None:
    order: list[str] = []
    retry_entered = Event()
    release_retry = Event()
    service = _ControllerService(
        order,
        [_shutdown_view(complete=False), _shutdown_view(complete=True)],
    )
    window = _ControllerWindow(order)

    def retry_prompt() -> bool:
        retry_entered.set()
        assert release_retry.wait(1.0)
        return True

    controller = host._DesktopCloseController(
        window,
        service,
        _close_hooks(order),
        window_title="NamiSync Test Close",
        render_status=lambda _window, _phase: None,
        retry_prompt=retry_prompt,
    )
    window.controller = controller
    controller._mark_loaded()
    original_start = controller._start_attempt
    claim_observed = Event()
    release_start = Event()

    def paused_start() -> None:
        claim_observed.set()
        assert release_start.wait(1.0)
        original_start()

    controller._start_attempt = paused_start

    # Start the first attempt without pausing its worker creation.
    controller._start_attempt = original_start
    assert controller._on_closing() is False
    assert retry_entered.wait(1.0)
    controller._start_attempt = paused_start
    release_retry.set()
    assert claim_observed.wait(1.0)

    assert not controller._attempt_done.is_set()
    waiter_done = Event()
    waiter = host.Thread(
        target=lambda: (controller._wait_for_attempt(), waiter_done.set()),
        daemon=True,
    )
    waiter.start()
    assert not waiter_done.wait(0.05)

    release_start.set()
    assert waiter_done.wait(1.0)
    assert service.close_count == 2
    assert window.destroy_count == 1


def test_worker_start_failure_cannot_block_the_closing_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_thread = host.Thread
    attempts = 0

    class FailedThread:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs

        def start(self) -> None:
            raise RuntimeError("synthetic thread-start failure")

    def first_start_fails(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return FailedThread()
        return real_thread(*args, **kwargs)

    order: list[str] = []
    prompt_visible = Event()
    window = _ControllerWindow(order)
    service = _ControllerService(order, [_shutdown_view(complete=True)])
    monkeypatch.setattr(host, "Thread", first_start_fails)
    monkeypatch.setattr(host, "_log_cleanup_failure", lambda *_args: None)
    controller = host._DesktopCloseController(
        window,
        service,
        _close_hooks(order),
        window_title="NamiSync Test Close",
        render_status=lambda _window, phase: order.append(
            f"status.{phase.value}"
        ),
        retry_prompt=lambda: prompt_visible.set() or False,
    )
    window.controller = controller
    controller._mark_loaded()

    started = monotonic()
    assert controller._on_closing() is False

    assert monotonic() - started < 0.1
    assert service.close_count == 0
    assert prompt_visible.wait(1.0)
    assert "status.retryable" in order


def test_user_close_during_startup_waits_for_loaded_guard_success() -> None:
    order: list[str] = []
    window = _ControllerWindow(order)
    service = _ControllerService(order, [_shutdown_view(complete=True)])
    controller = host._DesktopCloseController(
        window,
        service,
        _close_hooks(order),
        window_title="NamiSync Test Close",
        render_status=lambda _window, _phase: None,
        retry_prompt=lambda: False,
    )
    window.controller = controller

    assert controller._on_closing() is False
    assert service.close_count == 0
    assert window.destroy_count == 0

    controller._mark_loaded()
    assert window.destroyed.wait(1.0)
    assert service.close_count == 1


def test_user_close_during_startup_refusal_uses_the_startup_finalizer() -> None:
    order: list[str] = []
    window = _ControllerWindow(order)
    service = _ControllerService(order, [_shutdown_view(complete=True)])
    controller = host._DesktopCloseController(
        window,
        service,
        _close_hooks(order),
        window_title="NamiSync Test Close",
        render_status=lambda _window, _phase: None,
        retry_prompt=lambda: False,
    )
    window.controller = controller

    assert controller._on_closing() is False
    assert controller._mark_startup_refused()
    window.destroy()

    assert window.destroy_count == 1
    assert service.close_count == 0
    assert controller._on_closing() is None


def test_destroy_exception_after_complete_shutdown_never_retries_service() -> None:
    order: list[str] = []

    class FailedDestroyWindow(_ControllerWindow):
        def destroy(self) -> None:
            self.order.append("destroy")
            self.destroy_count += 1
            raise RuntimeError("synthetic destroy failure")

    window = FailedDestroyWindow(order)
    service = _ControllerService(order, [_shutdown_view(complete=True)])
    controller = host._DesktopCloseController(
        window,
        service,
        _close_hooks(order),
        window_title="NamiSync Test Close",
        render_status=lambda _window, _phase: None,
        retry_prompt=lambda: pytest.fail("complete shutdown requested a retry"),
    )
    window.controller = controller
    controller._mark_loaded()

    assert controller._on_closing() is False
    controller._wait_for_attempt()

    assert controller.service_shutdown_complete
    assert controller._on_closing() is None
    assert service.close_count == 1
    assert window.destroy_count == 1


def test_startup_refused_close_bypasses_the_user_close_worker() -> None:
    order: list[str] = []
    window = _ControllerWindow(order)
    service = _ControllerService(order, [_shutdown_view(complete=True)])
    controller = host._DesktopCloseController(
        window,
        service,
        _close_hooks(order),
        window_title="NamiSync Test Close",
        render_status=lambda _window, _phase: None,
        retry_prompt=lambda: False,
    )
    window.controller = controller

    controller._mark_startup_refused()

    assert controller._on_closing() is None
    assert service.close_count == 0
    assert order == []


def test_normal_user_close_does_not_close_the_service_twice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def close_during_loop(webview, *, on_initialized, storage_path) -> None:
        del storage_path
        on_initialized()
        webview.window.events.loaded.emit()
        assert webview.window.events.closing.emit() == [False]
        assert webview.window.destroyed.wait(1.0)

    paths, order, _webview, _document, reports = _patch_primary(
        monkeypatch,
        tmp_path,
        start=close_during_loop,
    )

    result = run_desktop(paths, _identity(), startup_error=reports.append)

    assert result == 0
    assert reports == []
    assert order.count("service.close") == 1
    assert order.index("service.close") < order.index("shutdown_logging")


def test_close_status_uses_only_fixed_page_text() -> None:
    element = SimpleNamespace(text="Ready")
    selectors: list[str] = []
    window = SimpleNamespace(
        dom=SimpleNamespace(
            get_element=lambda selector: selectors.append(selector) or element
        )
    )

    host._render_close_status(window, host._ClosePhase.CLOSING)
    assert element.text == "Closing safely…"
    host._render_close_status(window, host._ClosePhase.RETRYABLE)

    assert selectors == ["#host-status", "#host-status"]
    assert element.text == (
        "Close did not finish. Choose Retry in the close dialog to try again."
    )


def test_close_status_binds_each_loaded_document_before_async_render() -> None:
    first = SimpleNamespace(text="first")
    second = SimpleNamespace(text="second")
    elements = iter((first, second))
    selectors: list[str] = []
    window = SimpleNamespace(
        dom=SimpleNamespace(
            get_element=lambda selector: selectors.append(selector)
            or next(elements)
        )
    )
    controller = host._DesktopCloseController(
        window,
        SimpleNamespace(),
        host._DesktopCloseHooks(
            reject_dispatch=lambda: None,
            wake_waiters=lambda: None,
            wait_for_handlers=lambda: None,
            unsubscribe_observations=lambda: None,
        ),
        window_title="NamiSync Test",
    )

    controller._mark_loaded()
    controller._mark_loaded()
    window.dom.get_element = lambda _selector: pytest.fail(
        "the close worker must not query a destroyed document"
    )
    with controller._lock:
        controller._phase = host._ClosePhase.CLOSING
    controller._show_status(host._ClosePhase.CLOSING)

    assert selectors == ["#host-status", "#host-status"]
    assert first.text == "first"
    assert second.text == "Closing safely\u2026"


def test_close_status_write_failure_is_sanitized_and_does_not_change_truth(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailedStatus:
        @property
        def text(self) -> str:
            return "Ready"

        @text.setter
        def text(self, _value: str) -> None:
            raise RuntimeError(r"C:\private\status-sentinel")

    window = SimpleNamespace(
        dom=SimpleNamespace(get_element=lambda _selector: FailedStatus())
    )
    controller = host._DesktopCloseController(
        window,
        SimpleNamespace(),
        host._DesktopCloseHooks(
            reject_dispatch=lambda: None,
            wake_waiters=lambda: None,
            wait_for_handlers=lambda: None,
            unsubscribe_observations=lambda: None,
        ),
        window_title="NamiSync Test",
    )
    controller._mark_loaded()
    with controller._lock:
        controller._phase = host._ClosePhase.CLOSING
    caplog.set_level("ERROR", logger="namisync")

    controller._show_status(host._ClosePhase.CLOSING)

    record = next(
        item
        for item in caplog.records
        if item.getMessage().startswith("shutdown.status_render_failed")
    )
    assert record.exc_info is None
    assert "RuntimeError" in record.getMessage()
    assert "status-sentinel" not in caplog.text
    assert "Traceback" not in caplog.text
    with controller._lock:
        assert controller._phase is host._ClosePhase.CLOSING


def test_missing_bound_close_status_does_not_block_loaded_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("ERROR", logger="namisync")
    controller = host._DesktopCloseController(
        SimpleNamespace(
            dom=SimpleNamespace(get_element=lambda _selector: None)
        ),
        SimpleNamespace(),
        host._DesktopCloseHooks(
            reject_dispatch=lambda: None,
            wake_waiters=lambda: None,
            wait_for_handlers=lambda: None,
            unsubscribe_observations=lambda: None,
        ),
        window_title="NamiSync Test",
    )

    controller._mark_loaded()

    with controller._lock:
        assert controller._phase is host._ClosePhase.OPEN
    assert "shutdown.status_target_unavailable" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_native_retry_prompt_is_owned_and_has_no_force_close_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []
    user32 = SimpleNamespace(
        FindWindowW=lambda class_name, title: calls.append(
            ("find", class_name, title)
        )
        or 714,
        MessageBoxW=lambda *arguments: calls.append(("message", *arguments))
        or host._ID_RETRY,
    )
    monkeypatch.setattr(host.ctypes, "windll", SimpleNamespace(user32=user32))

    assert host._show_retry_close_prompt("NamiSync Fixed Title")
    assert calls[0] == ("find", None, "NamiSync Fixed Title")
    assert calls[1][1:4] == (
        714,
        host._CLOSE_INCOMPLETE_MESSAGE,
        host._CLOSE_INCOMPLETE_CAPTION,
    )
    assert calls[1][4] & host._MB_RETRYCANCEL
