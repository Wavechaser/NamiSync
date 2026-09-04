"""Headless guards for the real headed child-process harness."""

from __future__ import annotations

import ast
import ctypes
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import _headed_host_child as host_child
import _headed_native as native
from _headed_native import require_absolute_local_test_root


PROJECT_ROOT = Path(__file__).parents[3]


class _ExpiredElement(Exception):
    HResult = -2147220991


@pytest.mark.parametrize("expired_at", ("root", "lookup"))
def test_uia_observation_loads_once_and_reacquires_the_owned_tree(
    monkeypatch: pytest.MonkeyPatch,
    expired_at: str,
) -> None:
    loads: list[str] = []
    roots: list[int] = []
    searches: list[tuple[object, object]] = []
    attempts = iter((expired_at, "found"))

    def from_handle(handle: int) -> object:
        roots.append(handle)
        outcome = next(attempts)
        if outcome == "root":
            raise _ExpiredElement("provider expired")

        def find_first(scope: object, condition: object) -> object:
            searches.append((scope, condition))
            if outcome == "lookup":
                raise _ExpiredElement("provider expired")
            return object()

        return SimpleNamespace(FindFirst=find_first)

    monkeypatch.setitem(
        sys.modules,
        "clr",
        SimpleNamespace(AddReference=loads.append),
    )
    monkeypatch.setitem(sys.modules, "System", SimpleNamespace(IntPtr=int))
    monkeypatch.setitem(
        sys.modules,
        "System.Windows.Automation",
        SimpleNamespace(
            AutomationElement=SimpleNamespace(
                FromHandle=from_handle,
                NameProperty="name",
            ),
            PropertyCondition=lambda prop, value: (prop, value),
            TreeScope=SimpleNamespace(Descendants="descendants"),
            ElementNotAvailableException=_ExpiredElement,
        ),
    )
    monkeypatch.setattr(host_child, "_user32", lambda: object())
    monkeypatch.setattr(
        host_child,
        "_window_identity",
        lambda *_args, **_kwargs: (7, 301),
    )

    observe, expired = host_child._prepare_uia_observation(41, "expected", 301)
    with pytest.raises(expired):
        observe()
    assert observe() is True
    assert roots == [41, 41]
    assert searches[-1] == ("descendants", ("name", "expected"))
    assert len(loads) == 1

    monkeypatch.setattr(
        host_child,
        "_window_identity",
        lambda *_args, **_kwargs: (7, 999),
    )
    with pytest.raises(RuntimeError, match="ownership changed"):
        observe()
    assert roots == [41, 41]


@pytest.mark.parametrize(
    ("attempts", "prepare_error", "code", "transients", "successful"),
    (
        ([_ExpiredElement("expired"), True], None, 0, 1, 1),
        ([_ExpiredElement("expired")] * 3, None, 1, 3, 0),
        ([_ExpiredElement("expired"), False, False], None, 1, 1, 2),
        ([RuntimeError("provider broken")], None, 2, 0, 0),
        ([], ImportError("runtime unavailable"), 2, 0, 0),
    ),
)
def test_uia_probe_reports_retry_success_timeout_and_infrastructure_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    attempts: list[object],
    prepare_error: Exception | None,
    code: int,
    transients: int,
    successful: int,
) -> None:
    now = 0.0
    pending = list(attempts)

    def prepare(*_args: object) -> tuple[object, type[Exception]]:
        if prepare_error is not None:
            raise prepare_error

        def observe() -> bool:
            value = pending.pop(0)
            if isinstance(value, Exception):
                raise value
            return bool(value)

        return observe, _ExpiredElement

    def sleep(seconds: float) -> None:
        nonlocal now
        now += seconds

    monkeypatch.setattr(host_child, "_prepare_uia_observation", prepare)
    monkeypatch.setattr(
        host_child,
        "time",
        SimpleNamespace(monotonic=lambda: now, sleep=sleep),
    )
    actual = host_child._run_uia_probe(
        [
            "--handle",
            "41",
            "--process-id",
            "301",
            "--expected",
            "expected",
            "--deadline",
            "0.21",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert actual == code
    assert result["names"] == (["expected"] if code == 0 else [])
    assert result["transient_count"] == transients
    assert result["successful_observations"] == successful
    if transients:
        assert result["last_transient"] == {
            "type": "_ExpiredElement",
            "message": "expired",
            "hresult": -2147220991,
        }
    if code == 2:
        assert result["error"]["type"] == type(
            prepare_error or attempts[0]
        ).__name__
        assert now == 0


def test_uia_parent_preserves_owner_deadline_diagnostics_and_exact_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    process = object()
    completed = SimpleNamespace(
        returncode=0,
        stderr="",
        stdout=json.dumps(
            {
                "names": ["expected"],
                "transient_count": 2,
                "successful_observations": 3,
                "last_transient": {
                    "type": "Expired",
                    "message": "gone",
                    "hresult": 17,
                },
            }
        ),
    )

    def start(command: tuple[object, ...], **kwargs: object) -> object:
        captured["command"] = command
        captured["start_deadline"] = kwargs["deadline"]
        return process

    def wait(child: object, **kwargs: object) -> object:
        assert child is process
        captured["wait_deadline"] = kwargs["deadline"]
        return completed

    monkeypatch.setattr(
        native,
        "time",
        SimpleNamespace(monotonic=lambda: 100.0),
    )
    monkeypatch.setattr(native, "_window_process_id", lambda _handle: 301)
    monkeypatch.setattr(native, "start_headed_process", start)
    monkeypatch.setattr(native, "wait_for_process", wait)
    deadline = native.ScenarioDeadline(110.0)

    assert native.wait_for_accessible_text(
        41,
        "expected",
        python=Path(sys.executable),
        deadline=deadline,
    ) == ("expected",)
    command = captured["command"]
    assert command[command.index("--process-id") + 1] == "301"
    assert float(command[command.index("--deadline") + 1]) == 109.0
    assert captured["start_deadline"] is captured["wait_deadline"] is deadline

    for returncode, names in ((1, ["expected"]), (0, ["other"])):
        completed.returncode = returncode
        completed.stdout = json.dumps(
            {
                "names": names,
                "transient_count": 2,
                "successful_observations": 3,
                "last_transient": {
                    "type": "Expired",
                    "message": "gone",
                    "hresult": 17,
                },
            }
        )
        with pytest.raises(
            AssertionError,
            match="UI Automation did not expose",
        ) as failure:
            native.wait_for_accessible_text(
                41,
                "expected",
                python=Path(sys.executable),
                deadline=deadline,
            )
        assert "'transient_count': 2" in str(failure.value)
        assert "'successful_observations': 3" in str(failure.value)
        assert "'hresult': 17" in str(failure.value)

    starts = captured["command"]
    monkeypatch.setattr(native, "_window_process_id", lambda _handle: 0)
    with pytest.raises(AssertionError, match="window no longer exists"):
        native.wait_for_accessible_text(
            41,
            "expected",
            python=Path(sys.executable),
            deadline=deadline,
        )
    monkeypatch.setattr(native, "_window_process_id", lambda _handle: 301)
    with pytest.raises(AssertionError, match="no observation/reporting budget"):
        native.wait_for_accessible_text(
            41,
            "expected",
            python=Path(sys.executable),
            deadline=native.ScenarioDeadline(100.5),
        )
    assert captured["command"] is starts


@pytest.mark.parametrize(
    "value",
    [
        Path("relative"),
        Path(r"\\server\share\NamiSync"),
        Path("/posix-spelling"),
    ],
)
def test_headed_parent_refuses_nonlocal_or_non_drive_spelling(value: Path) -> None:
    with pytest.raises(ValueError, match="absolute local drive"):
        require_absolute_local_test_root(value, drive_type=lambda _path: 3)


def test_sh_g_2_only_paths_module_reads_the_production_root_authority() -> None:
    web_root = PROJECT_ROOT / "namisync" / "interfaces" / "web"
    sources = (
        PROJECT_ROOT / "namisync" / "interfaces" / "launcher.py",
        *web_root.rglob("*.py"),
    )
    local_app_data_readers: set[Path] = set()
    product_path_owners: set[Path] = set()
    for source in sources:
        text = source.read_text(encoding="utf-8")
        if "LOCALAPPDATA" in text:
            local_app_data_readers.add(source)
        tree = ast.parse(text, filename=str(source))
        for node in ast.walk(tree):
            if _uses_product_path_component(node):
                product_path_owners.add(source)

    expected = {web_root / "paths.py"}
    assert local_app_data_readers == expected
    assert product_path_owners == expected


def _uses_product_path_component(node: ast.AST) -> bool:
    if not any(
        isinstance(child, ast.Constant) and child.value == "NamiSync"
        for child in ast.walk(node)
    ):
        return False
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return True
    if not isinstance(node, ast.Call):
        return False
    function = node.func
    name = (
        function.id
        if isinstance(function, ast.Name)
        else function.attr
        if isinstance(function, ast.Attribute)
        else ""
    )
    return name in {"Path", "PurePath", "join", "joinpath"}


def test_headed_parent_refuses_a_mapped_remote_drive() -> None:
    with pytest.raises(ValueError, match="absolute local drive"):
        require_absolute_local_test_root(
            Path(r"Z:\NamiSync-Test"),
            drive_type=lambda _path: 4,
        )


def test_headed_parent_rechecks_locality_after_resolution(
    tmp_path: Path,
) -> None:
    path = tmp_path / "isolated"
    observed = iter((3, 4))

    with pytest.raises(ValueError, match="absolute local drive"):
        require_absolute_local_test_root(
            path,
            drive_type=lambda _path: next(observed),
        )


def test_exit_or_dialog_returns_new_dialog_before_process_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = SimpleNamespace(
        pid=700,
        poll=lambda: None,
        process_ids=lambda: frozenset({700, 701}),
    )
    monkeypatch.setattr(
        native,
        "_find_window",
        lambda caption, exclude, *, process_ids: 731,
    )

    completed, dialog = native.wait_for_exit_or_dialog(
        process,
        "NamiSync - Startup Error",
        exclude=frozenset({700}),
        deadline=native.scenario_deadline(0.1),
    )

    assert completed is None
    assert dialog == 731


def test_exit_or_dialog_returns_completed_child_without_waiting_for_dialog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[bool] = []
    child = SimpleNamespace(
        communicate=lambda *, timeout: ("", ""),
        returncode=None,
    )
    process = SimpleNamespace(
        pid=700,
        command=("synthetic-child",),
        process=child,
        poll=lambda: 0,
        process_ids=lambda: frozenset({700, 701}),
        close_job=lambda: closed.append(True),
    )
    monkeypatch.setattr(
        native,
        "_find_window",
        lambda caption, exclude, *, process_ids: None,
    )

    completed, dialog = native.wait_for_exit_or_dialog(
        process,
        "NamiSync - Startup Error",
        deadline=native.scenario_deadline(0.1),
    )

    assert completed is not None
    assert completed.returncode == 0
    assert dialog is None
    assert closed == [True]


def test_terminate_process_tree_closes_job_before_bounded_redirector_reap() -> None:
    calls: list[object] = []
    child = SimpleNamespace(
        poll=lambda: None,
        kill=lambda: calls.append("redirector"),
        communicate=lambda *, timeout: calls.append(("communicate", timeout)),
        stdout=None,
        stderr=None,
    )
    process = SimpleNamespace(
        pid=100,
        process=child,
        poll=lambda: None,
        close_job=lambda: calls.append("job"),
    )

    native.terminate_process_tree(
        process,
        deadline=native.ScenarioDeadline(native.time.monotonic() + 10.0),
    )

    assert calls == ["job", "redirector", ("communicate", 3.0)]


def test_process_tree_window_lookup_ignores_unrelated_matching_caption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(native, "_enumerate_windows", lambda: (70, 71))
    monkeypatch.setattr(native, "_window_text", lambda handle: "Same Caption")
    monkeypatch.setattr(native, "_is_window_visible", lambda handle: True)
    monkeypatch.setattr(
        native,
        "_window_process_id",
        lambda handle: {70: 900, 71: 701}[handle],
    )

    assert native._find_window(
        "Same Caption",
        frozenset(),
        process_ids=frozenset({700, 701}),
    ) == 71


def test_process_tree_window_lookup_ignores_hidden_matching_caption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(native, "_enumerate_windows", lambda: (70, 71))
    monkeypatch.setattr(native, "_window_text", lambda handle: "Same Caption")
    monkeypatch.setattr(
        native,
        "_is_window_visible",
        lambda handle: handle == 71,
    )
    monkeypatch.setattr(native, "_window_process_id", lambda handle: 700)

    assert native._find_window(
        "Same Caption",
        frozenset(),
        process_ids=frozenset({700}),
    ) == 71


def test_job_membership_tracks_processes_without_parentage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeKernel32:
        @staticmethod
        def QueryInformationJobObject(
            job_handle,
            information_class,
            buffer,
            buffer_size,
            returned,
        ) -> bool:
            assert job_handle == 44
            assert information_class == 3
            header = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_uint32))
            header[0] = 2
            header[1] = 2
            process_ids = ctypes.cast(
                ctypes.addressof(buffer._obj) + 8,
                ctypes.POINTER(ctypes.c_size_t),
            )
            process_ids[0] = 700
            process_ids[1] = 811
            ctypes.cast(returned, ctypes.POINTER(ctypes.c_uint32))[0] = buffer_size
            return True

    monkeypatch.setattr(native, "_kernel32", lambda: FakeKernel32())

    assert native._job_process_ids(44) == frozenset({700, 811})


def test_headed_source_never_targets_the_shared_production_desktop() -> None:
    web_tests = Path(native.__file__).parent
    slice_source = (web_tests / "test_slice1_headed.py").read_text(
        encoding="utf-8",
    )
    helper_sources = tuple(
        web_tests / name
        for name in (
            "_headed_host_child.py",
            "_headed_native.py",
            "_native_gate_child.py",
            "test_native_host_gates.py",
        )
    )

    assert 'window_handles("NamiSync")' not in slice_source
    assert "require_mutex_available" not in slice_source
    assert "Local\\NamiSync.Desktop" in slice_source
    assert "--test-mutex" in slice_source
    assert "--test-title" in slice_source
    for path in helper_sources:
        source = path.read_text(encoding="utf-8")
        assert "Local\\NamiSync.Desktop" not in source
        assert 'window_handles("NamiSync")' not in source

    tree = ast.parse(slice_source)
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        name = (
            call.func.id
            if isinstance(call.func, ast.Name)
            else call.func.attr
            if isinstance(call.func, ast.Attribute)
            else ""
        )
        if name not in {"start_headed_process", "_start_injected_host"}:
            continue
        literals = {
            child.value
            for child in ast.walk(call)
            if isinstance(child, ast.Constant) and isinstance(child.value, str)
        }
        assert r"Local\NamiSync.Desktop" not in literals
        assert "NamiSync" not in literals
