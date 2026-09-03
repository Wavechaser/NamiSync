"""Installed-wheel headed evidence for the Slice 2 transport boundary."""

from __future__ import annotations

import inspect
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import _headed_host_child as headed_host_child
import _transport_gate_child as transport_gate_child
from conftest import HeadedInstalledWheel
from namisync.version import NICKNAME, VERSION
from _headed_evidence import EvidencePaths, EvidencePublisher, EvidenceReader
from _startup_test_support import headed_command_extension
from _headed_native import (
    clean_child_environment,
    close_window,
    directory_snapshot,
    read_text,
    require_absolute_local_test_root,
    scenario_deadline,
    select_folder_in_native_dialog,
    start_headed_process,
    terminate_process_tree,
    wait_for_accessible_text,
    wait_for_initial_evidence,
    wait_for_process,
    wait_for_window,
)


_CHILD = Path(__file__).with_name("_transport_gate_child.py")
_TEST_ASSETS = Path(__file__).parents[2] / "assets" / "transport_gate"
_BOOTSTRAP_DRIVER = _TEST_ASSETS.parent / "bootstrap_test_bridge.js"
_PRODUCTION_ASSETS = (
    "bridge.js",
    "readiness.js",
    "render.js",
)
_BRIDGE_UNAVAILABLE = {
    "schema_version": 1,
    "request_id": None,
    "ok": False,
    "error": {
        "code": "bridge_unavailable",
        "message": (
            "NamiSync is closing or this desktop page is no longer trusted."
        ),
    },
}
_TRANSPORT_FINAL_KEYS = frozenset(
    {
        "browser_gate_server",
        "child_failure",
        "controlled_service_cleanup",
        "drain_exit",
        "drain_exited",
        "exit_code",
        "final_document_url",
        "next_event_responses",
        "raw_dispatch_bodies",
    }
)
_OFF_ORIGIN_FINAL_KEYS = frozenset(
    {"child_failure", "exit_code", "final_document_url"}
)


@dataclass(frozen=True, slots=True)
class _TransportEvidence:
    root: Path
    source: Path
    target: Path
    corpus: str
    body_marker: str
    path_sentinel: str
    result: dict[str, object]
    log_text: str
    picker_automation: tuple[dict[str, object], dict[str, object]]
    source_before: tuple[tuple[object, ...], ...]
    source_after: tuple[tuple[object, ...], ...]
    target_before: tuple[tuple[object, ...], ...]
    target_after: tuple[tuple[object, ...], ...]


@dataclass(frozen=True, slots=True)
class _OffOriginEvidence:
    root: Path
    result: dict[str, object]


@dataclass(slots=True)
class _HeadedTransportEvidence:
    installed: HeadedInstalledWheel
    root: Path
    installed_assets: Path
    transport_value: _TransportEvidence | None = None
    off_origin_value: _OffOriginEvidence | None = None
    transport_error: BaseException | None = None
    off_origin_error: BaseException | None = None

    @property
    def installed_root(self) -> Path:
        return self.installed.root.resolve()

    def transport(self) -> _TransportEvidence:
        if self.transport_error is not None:
            raise self.transport_error
        if self.transport_value is None:
            try:
                self.transport_value = _run_transport_scenario(
                    self.installed,
                    root=require_absolute_local_test_root(self.root / "transport"),
                    installed_assets=self.installed_assets,
                )
            except BaseException as error:
                self.transport_error = error
                raise
        return self.transport_value

    def off_origin(self) -> _OffOriginEvidence:
        if self.off_origin_error is not None:
            raise self.off_origin_error
        if self.off_origin_value is None:
            try:
                self.off_origin_value = _run_off_origin_scenario(
                    self.installed,
                    root=require_absolute_local_test_root(self.root / "off-origin"),
                    installed_assets=self.installed_assets,
                )
            except BaseException as error:
                self.off_origin_error = error
                raise
        return self.off_origin_value


@pytest.fixture(scope="session")
def headed_transport_evidence(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path_factory: pytest.TempPathFactory,
) -> _HeadedTransportEvidence:
    root = require_absolute_local_test_root(
        tmp_path_factory.mktemp("transport-headed")
    )
    installed_assets = _installed_asset_root(headed_installed_wheel)
    return _HeadedTransportEvidence(
        installed=headed_installed_wheel,
        root=root,
        installed_assets=installed_assets,
    )


def test_headed_transport_evidence_runs_each_requested_scenario_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    installed = HeadedInstalledWheel(
        wheel=tmp_path / "namisync.whl",
        root=tmp_path / "installed",
        python=tmp_path / "python.exe",
        scripts=tmp_path / "Scripts",
    )
    installed_assets = tmp_path / "assets"
    transport = object()
    off_origin = object()
    transport_failure = RuntimeError("transport failed after creating its root")
    off_origin_failure = RuntimeError(
        "off-origin failed after creating its root"
    )
    calls: list[tuple[str, Path, Path]] = []

    def run_transport(
        observed_installed: HeadedInstalledWheel,
        *,
        root: Path,
        installed_assets: Path,
    ) -> _TransportEvidence:
        assert observed_installed is installed
        calls.append(("transport", root, installed_assets))
        if root.parent.name == "transport-failure":
            root.mkdir(parents=True)
            raise transport_failure
        return transport  # type: ignore[return-value]

    def run_off_origin(
        observed_installed: HeadedInstalledWheel,
        *,
        root: Path,
        installed_assets: Path,
    ) -> _OffOriginEvidence:
        assert observed_installed is installed
        calls.append(("off-origin", root, installed_assets))
        if root.parent.name == "off-origin-failure":
            root.mkdir(parents=True)
            raise off_origin_failure
        return off_origin  # type: ignore[return-value]

    monkeypatch.setitem(globals(), "_run_transport_scenario", run_transport)
    monkeypatch.setitem(globals(), "_run_off_origin_scenario", run_off_origin)
    evidence = _HeadedTransportEvidence(installed, tmp_path, installed_assets)

    assert calls == []
    assert evidence.transport() is transport
    assert evidence.transport() is transport
    assert calls == [("transport", tmp_path / "transport", installed_assets)]
    assert evidence.off_origin() is off_origin
    assert evidence.off_origin() is off_origin
    assert calls == [
        ("transport", tmp_path / "transport", installed_assets),
        ("off-origin", tmp_path / "off-origin", installed_assets),
    ]

    failing_transport = _HeadedTransportEvidence(
        installed,
        tmp_path / "transport-failure",
        installed_assets,
    )
    with pytest.raises(RuntimeError) as first_transport:
        failing_transport.transport()
    with pytest.raises(RuntimeError) as second_transport:
        failing_transport.transport()
    assert first_transport.value is transport_failure
    assert second_transport.value is transport_failure

    failing_off_origin = _HeadedTransportEvidence(
        installed,
        tmp_path / "off-origin-failure",
        installed_assets,
    )
    with pytest.raises(RuntimeError) as first_off_origin:
        failing_off_origin.off_origin()
    with pytest.raises(RuntimeError) as second_off_origin:
        failing_off_origin.off_origin()
    assert first_off_origin.value is off_origin_failure
    assert second_off_origin.value is off_origin_failure
    assert calls.count(
        (
            "transport",
            tmp_path / "transport-failure" / "transport",
            installed_assets,
        )
    ) == 1
    assert calls.count(
        (
            "off-origin",
            tmp_path / "off-origin-failure" / "off-origin",
            installed_assets,
        )
    ) == 1


def test_transport_recorder_freezes_ready_and_publishes_only_shutdown_delta(
    tmp_path: Path,
) -> None:
    paths = EvidencePaths(tmp_path.resolve())
    recorder = transport_gate_child._Recorder(
        EvidencePublisher(paths),
        "transport",
    )
    recorder.set("events", [{"phase": "ready"}])
    recorder.publish_ready()
    recorder.append("events", {"phase": "shutdown"})
    recorder.set("exit_code", 0)
    recorder.publish_final()

    reader = EvidenceReader(paths)
    assert reader.read_ready() == {
        "events": [{"phase": "ready"}],
        "mode": "transport",
        "schema_version": 1,
        "startup_errors": [],
    }
    assert reader.read_final() == {
        "events": [{"phase": "ready"}, {"phase": "shutdown"}],
        "exit_code": 0,
    }
    reader.assert_consistent(require_final=True)


def test_transport_recorder_publishes_startup_error_as_failure(
    tmp_path: Path,
) -> None:
    paths = EvidencePaths(tmp_path.resolve())
    recorder = transport_gate_child._Recorder(
        EvidencePublisher(paths),
        "off-origin",
    )

    recorder.startup_error("startup refused")

    reader = EvidenceReader(paths)
    assert reader.available_initial() == "failure"
    assert reader.read_failure() == {
        "mode": "off-origin",
        "schema_version": 1,
        "startup_errors": ["startup refused"],
    }
    reader.assert_consistent(require_final=False)


@pytest.mark.parametrize("fixture", ("initial", "items", "terminal"))
def test_transport_gate_live_fixtures_use_typed_public_views(fixture: str) -> None:
    from namisync.workflows.views import (
        SessionEventView,
        validate_session_record_view,
    )

    session_id = "d" * 32
    if fixture == "initial":
        events = []
        transport_gate_child._deliver_initial_events(
            events.append,
            session_id,
        )
        assert all(type(event) is SessionEventView for event in events)
        assert [event.body_type for event in events] == [
            "StateChanged", "Progress",
        ]
    elif fixture == "items":
        events = []
        transport_gate_child._deliver_result_items(
            events.append,
            session_id,
            "hostile-海",
        )
        assert [event.body_type for event in events] == [
            "ItemOutcome", "IntegrityOutcome",
        ]
        assert all(type(event) is SessionEventView for event in events)
    else:
        validate_session_record_view(
            transport_gate_child._terminal_record(session_id)
        )


def test_transport_final_merge_rejects_a_boolean_exit_code() -> None:
    with pytest.raises(AssertionError):
        _merge_final_evidence(
            {"phase": "ready"},
            {"exit_code": False},
            allowed_keys=frozenset({"exit_code"}),
        )


def test_transport_gate_assets_keep_test_implementation_outside_package() -> None:
    child = _CHILD.read_text(encoding="utf-8")
    bootstrap = _BOOTSTRAP_DRIVER.read_text(encoding="utf-8")
    scripts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(_TEST_ASSETS.glob("*.js"))
    )

    compile(child, str(_CHILD), "exec")
    assert _TEST_ASSETS.is_relative_to(Path(__file__).parents[2] / "assets")
    assert '"test_report"' in child
    assert 'const REPORT_COMMAND = "test_report";' in scripts
    assert "window.pywebview" not in scripts
    assert "evaluate_js" not in child
    assert "evaluate_js" not in scripts
    assert "dispatchInteractive" in scripts
    assert "startTaskDrain" in scripts
    assert 'import("./bridge.js")' in scripts
    assert 'import("./bootstrap_test_bridge.js")' in scripts
    transport = (_TEST_ASSETS / "transport.js").read_text(encoding="utf-8")
    assert "function injectRendererOnlyReturnTableLoss()" in transport
    assert "function reincarnateBridge()" not in transport
    renderer_only = transport.split(
        "function injectRendererOnlyReturnTableLoss()", 1
    )[1].split("\n}", 1)[0]
    assert 'window.dispatchEvent(new Event("pywebviewready"));' in renderer_only
    assert "markBridgeOperational();" in renderer_only
    assert "acknowledgeShellReady" not in renderer_only
    assert "pickFolder(" in scripts
    assert "startPlan(" in scripts
    assert '"next_events"' in scripts
    assert "renderText(" in scripts
    assert 'id="host-status"' in (_TEST_ASSETS / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'id="host-status"' in (_TEST_ASSETS / "off_origin.html").read_text(
        encoding="utf-8"
    )
    assert 'id="host-status"' in (
        _TEST_ASSETS / "off_origin_start.html"
    ).read_text(encoding="utf-8")

    for name in ("transport.js", "off_origin_start.js"):
        startup = (_TEST_ASSETS / name).read_text(encoding="utf-8")
        assert "installTestBridgeReadiness();" in startup
        assert "await bootstrapTestBridge();" in startup
        assert "installAppearanceReceiver(" not in startup
    assert "pywebviewready" not in bootstrap
    assert "appearance" not in bootstrap.casefold()
    assert bootstrap.count("echoReadiness(challenge)") == 1
    assert "attempt < 2" in bootstrap
    assert bootstrap.index("installReadinessReceiver(") < bootstrap.index(
        "await whenBridgeApiReady();"
    )
    assert bootstrap.index("await whenBridgeApiReady();") < bootstrap.index(
        "await acknowledgeShellReady();"
    )
    assert bootstrap.index("await acknowledgeShellReady();") < bootstrap.index(
        "await readiness.whenReceivedAfter(readinessBaseline);"
    )
    assert bootstrap.index(
        "await readiness.whenReceivedAfter(readinessBaseline);"
    ) < bootstrap.index("markBridgeOperational();")


def test_transport_gate_uses_shared_immutable_command_composition() -> None:
    source = _CHILD.read_text(encoding="utf-8")
    helper = inspect.getsource(headed_command_extension)

    assert "headed_command_extension(" in source
    assert '"test_report": _test_spec(' in source
    assert "combined = MappingProxyType(" not in source
    assert "original_commands(" in helper
    assert "commands is not captured.get" in helper
    assert "startup_gate is not captured.get" in helper
    assert "MappingProxyType" in helper
    assert "register" not in source.casefold()
    assert "extra_commands" not in source


def test_transport_gate_native_picker_automation_is_exact_and_fail_closed() -> None:
    selection_source = inspect.getsource(
        headed_host_child._select_folder_with_automation
    )
    classifier_source = inspect.getsource(
        headed_host_child._classify_folder_dialog_controls
    )
    parent = Path(__file__).with_name("_headed_native.py").read_text(
        encoding="utf-8"
    )

    assert 'automation_id == "1152"' in classifier_source
    assert 'automation_id == "1"' in classifier_source
    assert headed_host_child._EDIT_CONTROL_TYPE == "ControlType.Edit"
    assert headed_host_child._BUTTON_CONTROL_TYPE == "ControlType.Button"
    assert "ControlType.Edit" not in selection_source
    assert "ControlType.Button" not in selection_source
    assert "ValuePattern.Pattern" in selection_source
    assert "_post_exact_folder_confirmation(" in selection_source
    assert "InvokePattern" not in selection_source
    target_source = inspect.getsource(
        headed_host_child._require_exact_folder_confirmation_target
    )
    post_source = inspect.getsource(
        headed_host_child._post_folder_confirmation_click
    )
    assert "NativeWindowHandle" in inspect.getsource(
        headed_host_child._post_exact_folder_confirmation
    )
    assert "IsWindow(button_handle)" in target_source
    assert "IsWindowVisible(button_handle)" in target_source
    assert "IsWindowEnabled(button_handle)" in target_source
    assert "_BUTTON_WINDOW_CLASS" in target_source
    assert "GetDlgCtrlID(button_handle)" in target_source
    assert "IsChild(dialog_handle, button_handle)" in target_source
    assert "button_process_id != process_id" in target_source
    assert "PostMessageW" in post_source
    assert headed_host_child._BM_CLICK == 0x00F5
    picker_sources = "\n".join(
        (
            selection_source,
            inspect.getsource(
                headed_host_child._post_exact_folder_confirmation
            ),
            target_source,
            post_source,
        )
    )
    for forbidden in (
        "SendInput",
        "SendKeys",
        "SetFocus",
        "SetActiveWindow",
        "SetForegroundWindow",
        "mouse_event",
        "keybd_event",
    ):
        assert forbidden not in picker_sources
    assert ".Current.Name" not in selection_source
    assert "process.process_ids()" in parent
    assert "_window_owner(handle) == owner_handle" in parent
    assert "require_absolute_local_test_root(path)" in parent


@pytest.mark.parametrize(
    "button_handle",
    (None, "not-a-handle", 0, -1),
)
def test_transport_gate_native_picker_refuses_invalid_native_handles(
    button_handle: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guarded: list[object] = []
    monkeypatch.setattr(
        headed_host_child,
        "_require_exact_folder_confirmation_target",
        lambda *args: guarded.append(args),
    )

    with pytest.raises(RuntimeError, match="has no native handle"):
        headed_host_child._post_exact_folder_confirmation(
            100,
            SimpleNamespace(
                Current=SimpleNamespace(NativeWindowHandle=button_handle)
            ),
            owner_handle=90,
            process_id=7,
        )

    assert guarded == []


def test_transport_gate_native_picker_refuses_failed_native_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guarded: list[tuple[int, ...]] = []
    posted: list[int] = []
    monkeypatch.setattr(
        headed_host_child,
        "_require_exact_folder_confirmation_target",
        lambda *args: guarded.append(args),
    )
    monkeypatch.setattr(
        headed_host_child,
        "_post_folder_confirmation_click",
        lambda handle: posted.append(handle) is None and False,
    )

    with pytest.raises(
        RuntimeError,
        match="failed to post folder confirmation click",
    ):
        headed_host_child._post_exact_folder_confirmation(
            100,
            SimpleNamespace(Current=SimpleNamespace(NativeWindowHandle=101)),
            owner_handle=90,
            process_id=7,
        )

    assert guarded == [(100, 101, 90, 7)]
    assert posted == [101]


class _FakeFolderDialogUser32:
    def __init__(self) -> None:
        self.windows = {100, 101}
        self.visible = {100, 101}
        self.enabled = {100, 101}
        self.owners = {100: 90}
        self.identities = {100: (8, 7), 101: (8, 7)}
        self.classes = {100: "#32770", 101: "Button"}
        self.control_ids = {101: 1}
        self.children = {(100, 101)}
        self.posts: list[tuple[int, int, int, int]] = []

    def IsWindow(self, handle: int) -> bool:
        return handle in self.windows

    def IsWindowVisible(self, handle: int) -> bool:
        return handle in self.visible

    def IsWindowEnabled(self, handle: int) -> bool:
        return handle in self.enabled

    def GetWindow(self, handle: int, _relation: int) -> int:
        return self.owners.get(handle, 0)

    def GetWindowThreadProcessId(self, handle: int, process: object) -> int:
        thread_id, process_id = self.identities.get(handle, (0, 0))
        process._obj.value = process_id
        return thread_id

    def GetClassNameW(self, handle: int, buffer: object, _length: int) -> int:
        value = self.classes.get(handle, "")
        buffer.value = value
        return len(value)

    def GetDlgCtrlID(self, handle: int) -> int:
        return self.control_ids.get(handle, 0)

    def IsChild(self, parent: int, child: int) -> bool:
        return (parent, child) in self.children

    def PostMessageW(
        self,
        handle: int,
        message: int,
        wparam: int,
        lparam: int,
    ) -> bool:
        self.posts.append((handle, message, wparam, lparam))
        return True


def test_transport_gate_native_picker_posts_to_validated_button(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = _FakeFolderDialogUser32()
    monkeypatch.setattr(headed_host_child, "_user32", lambda: native)

    headed_host_child._require_exact_folder_confirmation_target(100, 101, 90, 7)
    assert headed_host_child._post_folder_confirmation_click(101) is True

    assert native.posts == [(101, headed_host_child._BM_CLICK, 0, 0)]


@pytest.mark.parametrize(
    "defect",
    (
        "not_live",
        "not_visible",
        "not_enabled",
        "wrong_class",
        "wrong_control_id",
        "outside_dialog",
        "wrong_thread",
        "wrong_process",
    ),
)
def test_transport_gate_native_picker_rejects_untrusted_button_target(
    defect: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = _FakeFolderDialogUser32()
    if defect == "not_live":
        native.windows.remove(101)
    elif defect == "not_visible":
        native.visible.remove(101)
    elif defect == "not_enabled":
        native.enabled.remove(101)
    elif defect == "wrong_class":
        native.classes[101] = "Edit"
    elif defect == "wrong_control_id":
        native.control_ids[101] = 2
    elif defect == "outside_dialog":
        native.children.clear()
    elif defect == "wrong_thread":
        native.identities[101] = (9, 7)
    elif defect == "wrong_process":
        native.identities[101] = (8, 9)
    monkeypatch.setattr(headed_host_child, "_user32", lambda: native)

    with pytest.raises(RuntimeError, match="button identity changed"):
        headed_host_child._require_exact_folder_confirmation_target(
            100,
            101,
            90,
            7,
        )

    assert native.posts == []


def test_transport_gate_redacted_uia_classifier_uses_programmatic_type_names() -> None:
    class UnequalControlType:
        def __init__(self, programmatic_name: str) -> None:
            self.ProgrammaticName = programmatic_name

        def __eq__(self, other: object) -> bool:
            del other
            return False

    class Elements:
        def __init__(self, values: list[object]) -> None:
            self._values = values
            self.Count = len(values)

        def __getitem__(self, index: int) -> object:
            return self._values[index]

    class Current:
        def __init__(self, control_type: str, automation_id: str) -> None:
            self.ControlType = UnequalControlType(control_type)
            self.AutomationId = automation_id

        @property
        def IsDefault(self) -> object:
            raise RuntimeError("property unavailable")

    def element(control_type: str, automation_id: str) -> object:
        return SimpleNamespace(
            Current=Current(control_type, automation_id)
        )

    window = element("ControlType.Window", "dialog")
    edit = element("ControlType.Edit", "1152")
    button = element("ControlType.Button", "1")

    selected_edit, selected_button, observed = (
        headed_host_child._classify_folder_dialog_controls(
            Elements([window, edit, button])
        )
    )

    assert selected_edit is edit
    assert selected_button is button
    assert observed == {
        "element_count": 3,
        "candidate_count": 2,
        "omitted_candidate_count": 0,
        "unique_candidate_count": 2,
        "omitted_unique_candidate_count": 0,
        "unreadable_count": 0,
        "category_counts": {
            "exact_id_1152": 1,
            "exact_id_1": 1,
            "edit": 0,
            "default_button": 0,
            "other_button": 0,
        },
        "candidates": [
            {
                "control_type": "ControlType.Edit",
                "automation_id": "1152",
                "is_default": None,
                "occurrences": 1,
            },
            {
                "control_type": "ControlType.Button",
                "automation_id": "1",
                "is_default": None,
                "occurrences": 1,
            },
        ],
    }


def test_transport_gate_uia_classifier_rejects_lookalikes_and_duplicates() -> None:
    class Current:
        def __init__(self, control_type: str, automation_id: str) -> None:
            self.ControlType = SimpleNamespace(ProgrammaticName=control_type)
            self.AutomationId = automation_id

        @property
        def IsDefault(self) -> object:
            raise RuntimeError("property unavailable")

        @property
        def Name(self) -> object:
            raise AssertionError("UIA Name must not be read")

        @property
        def Value(self) -> object:
            raise AssertionError("UIA Value must not be read")

        @property
        def Path(self) -> object:
            raise AssertionError("a path must not be read")

    class Elements:
        def __init__(self, values: list[object]) -> None:
            self._values = values
            self.Count = len(values)

        def __getitem__(self, index: int) -> object:
            return self._values[index]

    def element(control_type: str, automation_id: str) -> object:
        return SimpleNamespace(Current=Current(control_type, automation_id))

    search_edit = element("ControlType.Edit", "SearchEditBox")
    list_item = element("ControlType.ListItem", "1")
    selected_edit, selected_button, observed = (
        headed_host_child._classify_folder_dialog_controls(
            Elements([search_edit, list_item])
        )
    )

    assert selected_edit is None
    assert selected_button is None
    assert observed["category_counts"] == {
        "exact_id_1152": 0,
        "exact_id_1": 1,
        "edit": 1,
        "default_button": 0,
        "other_button": 0,
    }
    assert observed["candidates"] == [
        {
            "control_type": "ControlType.ListItem",
            "automation_id": "1",
            "is_default": None,
            "occurrences": 1,
        },
        {
            "control_type": "ControlType.Edit",
            "automation_id": "SearchEditBox",
            "is_default": None,
            "occurrences": 1,
        },
    ]

    duplicate_edit = element("ControlType.Edit", "1152")
    with pytest.raises(RuntimeError, match="multiple exact folder path edits"):
        headed_host_child._classify_folder_dialog_controls(
            Elements([duplicate_edit, duplicate_edit])
        )

    duplicate_button = element("ControlType.Button", "1")
    with pytest.raises(
        RuntimeError,
        match="multiple exact folder confirmation buttons",
    ):
        headed_host_child._classify_folder_dialog_controls(
            Elements([duplicate_button, duplicate_button])
        )


def test_transport_gate_uia_diagnostic_aggregates_and_ranks_unique_candidates() -> None:
    class Current:
        def __init__(
            self,
            control_type: str,
            automation_id: str,
            is_default: bool,
        ) -> None:
            self.ControlType = SimpleNamespace(ProgrammaticName=control_type)
            self.AutomationId = automation_id
            self.IsDefault = is_default

        @property
        def Name(self) -> object:
            raise AssertionError("UIA Name must not be read")

        @property
        def Value(self) -> object:
            raise AssertionError("UIA Value must not be read")

        @property
        def Path(self) -> object:
            raise AssertionError("a path must not be read")

    class Elements:
        def __init__(self, values: list[object]) -> None:
            self._values = values
            self.Count = len(values)

        def __getitem__(self, index: int) -> object:
            return self._values[index]

    def element(control_type: str, automation_id: str) -> object:
        return SimpleNamespace(
            Current=Current(control_type, automation_id, False)
        )

    irrelevant = [
        element("ControlType.Window", f"irrelevant-{index}")
        for index in range(100)
    ]
    other_buttons = [
        element("ControlType.Button", f"other-{index}")
        for index in range(30)
    ]
    default_buttons = [
        SimpleNamespace(
            Current=Current("ControlType.Button", f"default-{index}", True)
        )
        for index in range(4)
    ]
    edits = [
        element("ControlType.Edit", "\u2028" * 100)
        for _ in range(3)
    ]
    id_1 = element("ControlType.Custom", "1")
    id_1152 = element("ControlType.Custom", "1152")

    selected_edit, selected_button, observed = (
        headed_host_child._classify_folder_dialog_controls(
            Elements(
                [
                    *irrelevant,
                    *other_buttons,
                    *default_buttons,
                    *edits,
                    id_1,
                    id_1152,
                ]
            )
        )
    )

    assert selected_edit is None
    assert selected_button is None
    assert observed["element_count"] == 139
    assert observed["candidate_count"] == 39
    assert observed["omitted_candidate_count"] == 21
    assert observed["unique_candidate_count"] == 37
    assert observed["omitted_unique_candidate_count"] == 21
    assert observed["unreadable_count"] == 0
    assert observed["category_counts"] == {
        "exact_id_1152": 1,
        "exact_id_1": 1,
        "edit": 3,
        "default_button": 4,
        "other_button": 30,
    }
    observed_candidates = observed["candidates"]
    assert isinstance(observed_candidates, list)
    assert len(observed_candidates) == 16
    assert observed_candidates[0] == {
        "control_type": "ControlType.Custom",
        "automation_id": "1152",
        "is_default": False,
        "occurrences": 1,
    }
    assert observed_candidates[1] == {
        "control_type": "ControlType.Custom",
        "automation_id": "1",
        "is_default": False,
        "occurrences": 1,
    }
    assert observed_candidates[2] == {
        "control_type": "ControlType.Edit",
        "automation_id": "\u2028" * 32,
        "is_default": False,
        "occurrences": 3,
    }
    assert [
        candidate["automation_id"] for candidate in observed_candidates[3:7]
    ] == [f"default-{index}" for index in range(4)]
    assert [
        candidate["automation_id"] for candidate in observed_candidates[7:]
    ] == [f"other-{index}" for index in range(9)]
    assert all(
        candidate["occurrences"] == 1
        for candidate in [*observed_candidates[:2], *observed_candidates[3:]]
    )
    serialized = json.dumps(observed)
    assert "irrelevant" not in serialized
    assert "Name" not in serialized
    assert "Value" not in serialized
    assert "Path" not in serialized
    assert len(serialized.encode("utf-8")) < 8192


def test_transport_gate_uia_subcommands_parse_their_exact_headless_shapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe_source = inspect.getsource(headed_host_child._run_uia_probe)
    lookup_source = inspect.getsource(headed_host_child._automation_has_name)
    observed_probes: list[tuple[int, str]] = []

    def has_name(handle: int, expected: str) -> bool:
        observed_probes.append((handle, expected))
        return True

    monkeypatch.setattr(
        headed_host_child,
        "_automation_has_name",
        has_name,
    )
    assert headed_host_child._run_uia_probe(
        [
            "--handle",
            "41",
            "--expected",
            "expected",
            "--timeout",
            "0.1",
        ]
    ) == 0
    assert observed_probes == [(41, "expected")]
    assert "_automation_names" not in probe_source
    assert "FindFirst" in lookup_source
    assert "NameProperty" in lookup_source
    assert "FindAll" not in lookup_source

    observed: dict[str, object] = {}

    def select(
        handle: int,
        path: str,
        *,
        owner_handle: int,
        process_id: int,
        deadline: float,
    ) -> dict[str, object]:
        observed.update(
            {
                "handle": handle,
                "path": path,
                "owner_handle": owner_handle,
                "process_id": process_id,
                "deadline": deadline,
            }
        )
        return {"selected": True, "confirmation_posts": 1}

    monkeypatch.setattr(
        headed_host_child,
        "_select_folder_with_automation",
        select,
    )
    selected = tmp_path / "selected"
    assert headed_host_child._run_uia_select_folder(
        [
            "--handle",
            "42",
            "--owner-handle",
            "43",
            "--process-id",
            "44",
            "--path",
            str(selected),
            "--timeout",
            "0.1",
        ]
    ) == 0
    assert observed["handle"] == 42
    assert observed["path"] == str(selected)
    assert observed["owner_handle"] == 43
    assert observed["process_id"] == 44
    assert isinstance(observed["deadline"], float)


def test_transport_gate_off_origin_fault_removes_only_top_level_precommit_guard() -> None:
    source = _CHILD.read_text(encoding="utf-8")

    assert "core.NavigationStarting -= guard._on_navigation_starting" in source
    assert "FrameNavigationStarting -=" not in source
    assert "NewWindowRequested -=" not in source
    assert "SourceChanged -=" not in source
    assert "original_source_changed(guard, sender, event_args)" in source
    assert "ThreadingHTTPServer((\"127.0.0.1\", 0), handler)" in source


@pytest.mark.headed
def test_br_g_32_hostile_text_crosses_real_return_transport_and_production_text_sink(
    headed_transport_evidence: _HeadedTransportEvidence,
) -> None:
    evidence = headed_transport_evidence.transport()
    result = evidence.result
    report = result["report"]
    dom = report["dom"]

    assert report["observed"].encode("utf-8") == evidence.corpus.encode("utf-8")
    assert report["source_keys"] == ["display", "id"]
    assert report["target_keys"] == ["display", "id"]
    assert report["source_display"] == str(evidence.source)
    assert report["target_display"] == str(evidence.target)
    assert dom["element_children"] == 0
    assert dom["image_count"] == 0
    assert dom["script_count_after"] == dom["script_count_before"]
    assert dom["hostile_marker_defined"] is False
    assert result["production_command_names"] == [
        "close_task",
        "next_events",
        "pick_folder",
        "read_cosmetic_section",
        "readiness_echo",
        "release_terminal_session",
        "replace_cosmetic_section",
        "shell_ready",
        "start_plan",
    ]
    assert result["combined_command_names"] == [
        "close_task",
        "next_events",
        "pick_folder",
        "read_cosmetic_section",
        "readiness_echo",
        "release_terminal_session",
        "replace_cosmetic_section",
        "shell_ready",
        "start_plan",
        "test_report",
    ]
    assert result["combined_mapping_type"] == "mappingproxy"
    assert result["dispatcher_type"] == (
        "namisync.interfaces.web.bridge.BridgeDispatcher"
    )
    requests = [json.loads(body) for body in result["raw_dispatch_bodies"]]
    acknowledgements = [
        request for request in requests if request.get("command") == "shell_ready"
    ]
    assert len(acknowledgements) == 1
    assert acknowledgements[0]["payload"] == {}
    assert requests[0] == acknowledgements[0]
    assert result["pywebview_js_api_is_none"] is True
    assert result["pywebview_function_names"] == ["dispatch"]
    assert "https://attacker.invalid/" not in result.get("document_records", [])
    runtime = result["runtime"]
    assert Path(runtime["namisync_file"]).resolve().is_relative_to(
        headed_transport_evidence.installed_root
    )
    assert Path(runtime["executable"]).resolve().is_relative_to(
        headed_transport_evidence.installed_root
    )
    assert runtime["versions"] == {
        "namisync": VERSION,
        "pywebview": "6.2.1",
        "pythonnet": "3.1.0",
    }


@pytest.mark.headed
def test_br_g_32_native_picker_keeps_real_paths_in_server_slots(
    headed_transport_evidence: _HeadedTransportEvidence,
) -> None:
    evidence = headed_transport_evidence.transport()
    calls = evidence.result["service_start_plan_calls"]

    assert len(calls) == 5
    assert [
        (call["source"], call["target"], call["deletion_policy"])
        for call in calls
    ] == [
        (str(evidence.source), str(evidence.target), None),
        (str(evidence.source), str(evidence.target), "trash"),
        (str(evidence.source), str(evidence.target), "trash"),
        (str(evidence.source), str(evidence.target), "trash"),
        (str(evidence.source), str(evidence.target), "additive"),
    ]
    assert all(len(call["command_id"]) == 32 for call in calls)
    assert len({call["command_id"] for call in calls}) == len(calls)
    assert evidence.result["report"]["source_id"].startswith("slot-")
    assert evidence.result["report"]["target_id"].startswith("slot-")
    assert all(item["selected"] is True for item in evidence.picker_automation)
    assert all(
        item["confirmation_posts"] in {1, 2}
        for item in evidence.picker_automation
    )
    assert evidence.source_after == evidence.source_before
    assert evidence.target_after == evidence.target_before


@pytest.mark.headed
def test_br_g_32_origin_recheck_rejects_dispatch_independently(
    headed_transport_evidence: _HeadedTransportEvidence,
) -> None:
    result = headed_transport_evidence.off_origin().result

    assert result["navigation_starting_removed"] is True
    assert result["off_origin_response"] == _BRIDGE_UNAVAILABLE
    assert result["off_origin_handler_calls"] == []
    assert result["final_document_url"].startswith("http://127.0.0.1:")
    assert result["final_document_url"].endswith("/off_origin.html")
    assert result["final_document_url"] in result["committed_sources"]
    assert result["production_command_names"] == [
        "close_task",
        "next_events",
        "pick_folder",
        "read_cosmetic_section",
        "readiness_echo",
        "release_terminal_session",
        "replace_cosmetic_section",
        "shell_ready",
        "start_plan",
    ]
    assert result["dispatcher_type"] == (
        "namisync.interfaces.web.bridge.BridgeDispatcher"
    )
    requests = [json.loads(body) for body in result["raw_dispatch_bodies"]]
    acknowledgements = [
        request for request in requests if request.get("command") == "shell_ready"
    ]
    assert len(acknowledgements) == 1
    assert acknowledgements[0]["payload"] == {}
    assert requests[0] == acknowledgements[0]
    runtime = result["runtime"]
    assert Path(runtime["namisync_file"]).resolve().is_relative_to(
        headed_transport_evidence.installed_root
    )
    assert Path(runtime["executable"]).resolve().is_relative_to(
        headed_transport_evidence.installed_root
    )
    assert runtime["versions"] == {
        "namisync": VERSION,
        "pywebview": "6.2.1",
        "pythonnet": "3.1.0",
    }


@pytest.mark.headed
def test_br_g_33_real_next_events_is_concurrent_and_shutdown_wakes_it(
    headed_transport_evidence: _HeadedTransportEvidence,
) -> None:
    result = headed_transport_evidence.transport().result

    assert result["drain_probe_report"] == {
        "drain_entered": True,
        "drain_exited": False,
        "drain_settled": False,
    }
    assert result["drain_exit"] == {
        "type": "TaskUnavailableError",
        "message": "task is closing",
    }
    assert result["drain_exited"] is True


@pytest.mark.headed
def test_br_g_33_real_webview2_recovers_only_from_explicit_transport_evidence(
    headed_transport_evidence: _HeadedTransportEvidence,
) -> None:
    evidence = headed_transport_evidence.transport()
    result = evidence.result
    browser = result["report"]["browser_gate"]
    server = result["browser_gate_server"]

    assert browser["interactive_refusal"] == {
        "name": "BridgeCommandError",
        "code": "internal_error",
    }
    assert browser["accepted_types"] == [
        "StateChanged",
        "Progress",
        "Gap",
        "Gap",
        "PhaseChanged",
        "ItemOutcome",
        "IntegrityOutcome",
        "record",
    ]
    assert browser["accepted_sequences"] == [1, 3, 4, 4, 5, 6, 7]
    assert browser["busy_refusals"] == []
    assert browser["malformed_refusal"] == {
        "name": "BridgeTransportError"
    }
    assert browser["callback_release_order"] == ["record", "release"]
    assert browser["automatic_close_calls"] == 0
    assert browser["replacement_registration"] is True
    assert browser["cleanup"] == {
        "active_timers": 0,
        "ready_listeners": 1,
    }

    nested = browser["nested_record"]
    assert nested["session_id"] == "d" * 32
    assert nested["kind"] == "sync-plan"
    assert nested["state"] == "completed"
    assert "items" not in nested["result"]
    assert nested["result"]["bytes_done"] == "7"
    assert nested["result"]["bytes_total"] == "7"
    assert browser["nested_items"] == [
        {
            "item_type": "operation",
            "phase": "execute",
            "item_id": "1" * 32,
            "kind": "copy",
            "path": evidence.corpus,
            "result": "succeeded",
            "reason": None,
            "detail": {
                "message": evidence.corpus,
                "durability_warnings": ["海", "é", "U0001f30a"],
            },
            "recording": "ok",
            "recording_reason": None,
            "recording_detail": None,
            "detail_omitted_count": 0,
        },
        {
            "item_type": "integrity",
            "phase": "verify",
            "item_id": "integrity-hostile",
            "row_id": "row-hostile",
            "location_id": "location-hostile",
            "kind": "integrity",
            "path": evidence.corpus,
            "result": "verified",
            "reason": None,
            "detail": evidence.corpus,
            "read_strategy": "windows-unbuffered",
            "recording": "ok",
            "record_disposition": "applied",
            "detail_omitted_count": 0,
        },
    ]
    assert [phase["phase"] for phase in nested["result"]["phases"]] == [
        "execute",
        "verify",
    ]
    assert browser["nested_dom"] == {
        "observed": evidence.corpus,
        "element_children": 0,
        "image_count": 0,
        "hostile_marker_defined": False,
    }

    assert server["drain_cursors"][:4] == [
        {"role": "main", "replay_from": None},
        {"role": "main", "replay_from": 1},
        {"role": "main", "replay_from": None},
        {"role": "main", "replay_from": 4},
    ]
    assert server["interactive_failures"] == 1
    assert server["malformed_attempts"] == 7
    assert len(server["registry_release_calls"]) == 2
    assert len(server["registry_close_calls"]) == 2
    assert {
        cleanup[0]
        for cleanup in result["controlled_service_cleanup"]
    } == {"release_task_session", "close_task"}

    response_kinds = [
        (item["role"], item["kind"])
        for item in result["next_event_responses"]
    ]
    assert ("busy", "drain_busy") in response_kinds
    assert ("busy", "bridge_busy") in response_kinds
    assert ("busy", "success") in response_kinds
    malformed = [
        kind for role, kind in response_kinds if role == "malformed"
    ]
    assert malformed == ["authority_mismatch", *("malformed",) * 6]

    requests = [
        json.loads(body)
        for body in result["raw_dispatch_bodies"]
        if isinstance(body, str)
    ]
    start_requests = [
        request for request in requests if request.get("command") == "start_plan"
    ]
    by_command: dict[str, list[dict[str, object]]] = {}
    for request in start_requests:
        by_command.setdefault(request["payload"]["command_id"], []).append(request)
    replays = [attempts for attempts in by_command.values() if len(attempts) == 2]
    assert len(replays) == 1
    first, second = replays[0]
    assert first["request_id"] != second["request_id"]
    assert first["payload"] == second["payload"]
    assert set(first["payload"]) == {
        "command_id",
        "source_id",
        "target_id",
        "deletion_policy",
    }


@pytest.mark.headed
def test_sh_g_3_headed_renderer_and_hostile_dispatch_are_logged_safely(
    headed_transport_evidence: _HeadedTransportEvidence,
) -> None:
    evidence = headed_transport_evidence.transport()
    native_version = evidence.result["native_browser_version"]
    hostile_bodies = [
        body
        for body in evidence.result["raw_dispatch_bodies"]
        if evidence.body_marker in body
    ]

    assert native_version
    assert f"startup.renderer browser_version={native_version}" in evidence.log_text
    assert len(hostile_bodies) == 1
    assert hostile_bodies[0] not in evidence.log_text
    assert evidence.body_marker not in evidence.log_text
    assert evidence.path_sentinel not in evidence.log_text
    assert str(evidence.source) not in evidence.log_text
    assert str(evidence.target) not in evidence.log_text
    assert "Traceback (most recent call last)" not in evidence.log_text
    assert "exception=" not in evidence.log_text.casefold()
    assert NICKNAME not in evidence.log_text


def _run_transport_scenario(
    installed: HeadedInstalledWheel,
    *,
    root: Path,
    installed_assets: Path,
) -> _TransportEvidence:
    deadline = scenario_deadline(90.0)
    root.mkdir(parents=True)
    page = require_absolute_local_test_root(root / "page")
    _combine_page(page, installed_assets)
    source = require_absolute_local_test_root(root / "selected-source-海")
    target = require_absolute_local_test_root(root / "selected-target-川")
    source.mkdir()
    target.mkdir()
    source_before = directory_snapshot(source, deadline=deadline)
    target_before = directory_snapshot(target, deadline=deadline)
    token = uuid4().hex
    body_marker = f"HOSTILE-BODY-{token}"
    path_sentinel = rf"C:\Private\NamiSync-{token}\秘密\file.txt"
    corpus = (
        f"{body_marker}\r\n{path_sentinel}\n"
        "bad_\\udcff.txt\thostile%_[x]\\a&b.txt\r\n"
        "quotes=\\\"double\\\"/'single' & ampersand\n"
        "</script><img src=x onerror=globalThis.__namiHostileMarker=true>"
        " & < > \\\" ' ` ${} \u2028 \u2029 e\u0301 😀 نهاية"
    )
    scenario = require_absolute_local_test_root(root / "scenario.json")
    scenario.write_text(
        json.dumps(
            {
                "corpus": corpus,
                "body_marker": body_marker,
                "path_sentinel": path_sentinel,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    evidence_root = require_absolute_local_test_root(root / "evidence")
    evidence_root.mkdir()
    evidence_paths = EvidencePaths(evidence_root)
    evidence_reader = EvidenceReader(evidence_paths)
    data_root = require_absolute_local_test_root(root / "data")
    title = f"NamiSync Transport Test {token}"
    process = start_headed_process(
        (
            installed.python,
            _CHILD,
            "--mode",
            "transport",
            "--data-dir",
            data_root,
            "--index",
            require_absolute_local_test_root(page / "index.html"),
            "--mutex",
            rf"Local\NamiSync.Transport.Test.{token}",
            "--title",
            title,
            "--evidence",
            evidence_root,
            "--scenario",
            scenario,
        ),
        cwd=installed.root,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    picker_results: list[dict[str, object]] = []
    try:
        window = wait_for_window(process, title, deadline=deadline)
        picker_results.append(
            select_folder_in_native_dialog(
                process,
                window,
                source,
                python=installed.python,
                deadline=deadline,
            )
        )
        picker_results.append(
            select_folder_in_native_dialog(
                process,
                window,
                target,
                python=installed.python,
                deadline=deadline,
            )
        )
        milestone, interim = wait_for_initial_evidence(
            evidence_reader,
            process,
            deadline=deadline,
        )
        if milestone == "failure":
            evidence_reader.assert_consistent(require_final=False)
            browser_failure = interim.get("browser_failure")
            if browser_failure is not None:
                raise AssertionError(
                    f"transport browser gate failed: {browser_failure!r}"
                )
            raise AssertionError(
                f"transport headed harness failed: {interim!r}"
            )
        wait_for_accessible_text(
            window,
            "Transport gate complete",
            python=installed.python,
            deadline=deadline,
        )
        assert interim["report"]["observed"] == corpus
        calls = interim["service_start_plan_calls"]
        assert len(calls) == 5
        assert [
            (call["source"], call["target"], call["deletion_policy"])
            for call in calls
        ] == [
            (str(source), str(target), None),
            (str(source), str(target), "trash"),
            (str(source), str(target), "trash"),
            (str(source), str(target), "trash"),
            (str(source), str(target), "additive"),
        ]
        assert interim["drain_probe_report"] == {
            "drain_entered": True,
            "drain_exited": False,
            "drain_settled": False,
        }
        close_window(window)
        completed = wait_for_process(process, deadline=deadline)
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)
    final = evidence_reader.read_final()
    assert final is not None
    evidence_reader.assert_consistent(require_final=True)
    result = _merge_final_evidence(
        interim,
        final,
        allowed_keys=_TRANSPORT_FINAL_KEYS,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert result["exit_code"] == 0
    assert result["startup_errors"] == []
    assert result["runtime"]["versions"] == {
        "namisync": VERSION,
        "pywebview": "6.2.1",
        "pythonnet": "3.1.0",
    }
    return _TransportEvidence(
        root=root,
        source=source,
        target=target,
        corpus=corpus,
        body_marker=body_marker,
        path_sentinel=path_sentinel,
        result=result,
        log_text=read_text(data_root / "logs" / "namisync.log", deadline=deadline),
        picker_automation=(picker_results[0], picker_results[1]),
        source_before=source_before,
        source_after=directory_snapshot(source, deadline=deadline),
        target_before=target_before,
        target_after=directory_snapshot(target, deadline=deadline),
    )


def _run_off_origin_scenario(
    installed: HeadedInstalledWheel,
    *,
    root: Path,
    installed_assets: Path,
) -> _OffOriginEvidence:
    deadline = scenario_deadline(90.0)
    root.mkdir(parents=True)
    page = require_absolute_local_test_root(root / "page")
    _combine_page(page, installed_assets)
    scenario = require_absolute_local_test_root(root / "scenario.json")
    scenario.write_text("{}", encoding="utf-8")
    evidence_root = require_absolute_local_test_root(root / "evidence")
    evidence_root.mkdir()
    evidence_paths = EvidencePaths(evidence_root)
    evidence_reader = EvidenceReader(evidence_paths)
    data_root = require_absolute_local_test_root(root / "data")
    token = uuid4().hex
    title = f"NamiSync Origin Test {token}"
    process = start_headed_process(
        (
            installed.python,
            _CHILD,
            "--mode",
            "off-origin",
            "--data-dir",
            data_root,
            "--index",
            require_absolute_local_test_root(page / "off_origin_start.html"),
            "--mutex",
            rf"Local\NamiSync.Origin.Test.{token}",
            "--title",
            title,
            "--evidence",
            evidence_root,
            "--scenario",
            scenario,
        ),
        cwd=installed.root,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    try:
        window = wait_for_window(process, title, deadline=deadline)
        milestone, interim = wait_for_initial_evidence(
            evidence_reader,
            process,
            deadline=deadline,
        )
        if milestone == "failure":
            evidence_reader.assert_consistent(require_final=False)
            raise AssertionError(
                f"off-origin headed harness failed: {interim!r}"
            )
        wait_for_accessible_text(
            window,
            "Off-origin dispatch refused",
            python=installed.python,
            deadline=deadline,
        )
        assert interim["off_origin_response"] == _BRIDGE_UNAVAILABLE
        assert interim["off_origin_handler_calls"] == []
        assert any(
            source.startswith("http://127.0.0.1:")
            and source.endswith("/off_origin.html")
            for source in interim["committed_sources"]
        )
        close_window(window)
        completed = wait_for_process(process, deadline=deadline)
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)
    final = evidence_reader.read_final()
    assert final is not None
    evidence_reader.assert_consistent(require_final=True)
    result = _merge_final_evidence(
        interim,
        final,
        allowed_keys=_OFF_ORIGIN_FINAL_KEYS,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert result["exit_code"] == 0
    assert result["startup_errors"] == []
    assert result["runtime"]["versions"] == {
        "namisync": VERSION,
        "pywebview": "6.2.1",
        "pythonnet": "3.1.0",
    }
    return _OffOriginEvidence(root=root, result=result)


def _merge_final_evidence(
    ready: dict[str, object],
    final: dict[str, object],
    *,
    allowed_keys: frozenset[str],
) -> dict[str, object]:
    unexpected = set(final) - allowed_keys
    assert unexpected == set(), (
        f"headed final evidence changed unexpected fields: {sorted(unexpected)!r}"
    )
    assert "exit_code" in final
    assert type(final["exit_code"]) is int
    merged = dict(ready)
    merged.update(final)
    return merged


def _combine_page(page: Path, installed_assets: Path) -> None:
    page.mkdir(parents=True)
    for source in sorted(_TEST_ASSETS.iterdir()):
        if source.is_file():
            shutil.copy2(source, page / source.name)
    shutil.copy2(_BOOTSTRAP_DRIVER, page / _BOOTSTRAP_DRIVER.name)
    for name in _PRODUCTION_ASSETS:
        shutil.copy2(installed_assets / name, page / name)


def _installed_asset_root(installed: HeadedInstalledWheel) -> Path:
    root = (
        installed.root
        / "Lib"
        / "site-packages"
        / "namisync"
        / "interfaces"
        / "web"
        / "assets"
    ).resolve()
    assert root.is_dir()
    assert root.is_relative_to(installed.root.resolve())
    for name in _PRODUCTION_ASSETS:
        assert (root / name).is_file()
    return root
