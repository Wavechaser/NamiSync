"""Headless guards for the real headed child-process harness."""

from __future__ import annotations

import ast
import ctypes
from pathlib import Path
from types import SimpleNamespace

import pytest

import _headed_native as native
from _headed_native import require_absolute_local_test_root


PROJECT_ROOT = Path(__file__).parents[3]


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
