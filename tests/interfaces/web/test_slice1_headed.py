"""Real installed-wheel evidence for the Slice 1 desktop host."""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path
from uuid import uuid4

import pytest

from conftest import HeadedInstalledWheel
from _headed_evidence import EvidencePaths, EvidenceReader
from _headed_native import (
    HeadedProcess,
    ScenarioDeadline,
    clean_child_environment,
    close_window,
    dialog_text,
    directory_snapshot,
    dismiss_ok_dialog,
    foreground_window_handle,
    read_bytes,
    read_text,
    require_absolute_local_test_root,
    run_with_deadline,
    scenario_deadline,
    start_headed_process,
    terminate_process_tree,
    wait_for_accessible_text,
    wait_for_dialog_text,
    wait_for_exit_or_dialog,
    wait_for_initial_evidence,
    wait_for_process,
    wait_for_window,
    window_handles,
)


HOST_CHILD = Path(__file__).with_name("_headed_host_child.py")
pytestmark = pytest.mark.headed


def test_sh_g_1_entry_points_are_classified_by_the_operating_system(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path: Path,
) -> None:
    deadline = scenario_deadline()
    console = headed_installed_wheel.scripts / "nami-sync.exe"
    gui = headed_installed_wheel.scripts / "nami-sync-gui.exe"
    environment = clean_child_environment()

    for command in (
        [str(console)],
        [str(headed_installed_wheel.python), "-m", "namisync"],
    ):
        completed = run_with_deadline(
            command,
            deadline=deadline,
            cwd=headed_installed_wheel.root,
            env=environment,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        assert completed.stdout == ""
        assert completed.stderr.startswith("usage: nami-sync")
        assert "nami-sync-gui" in completed.stderr

    module_probe = """
import json
import sys
from pathlib import Path
from namisync.interfaces.launcher import main

code = main(["history", "--history-database", sys.argv[1]])
print("PROBE=" + json.dumps({
    "code": code,
    "modules": sorted(
        name for name in sys.modules
        if name == "webview" or name.startswith("webview.")
    ),
    "module_file": __import__("namisync").__file__,
}))
raise SystemExit(code)
"""
    explicit = run_with_deadline(
        [
            str(headed_installed_wheel.python),
            "-c",
            module_probe,
            str(tmp_path / "history.db"),
        ],
        deadline=deadline,
        cwd=headed_installed_wheel.root,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert explicit.returncode == 0, explicit.stdout + explicit.stderr
    result = json.loads(
        next(
            line.removeprefix("PROBE=")
            for line in explicit.stdout.splitlines()
            if line.startswith("PROBE=")
        )
    )
    assert result["code"] == 0
    assert result["modules"] == []
    assert Path(result["module_file"]).is_relative_to(headed_installed_wheel.root)

    assert _pe_subsystem(gui, deadline=deadline) == 2


def test_sh_g_6_installed_wheel_packaged_page_smoke(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path: Path,
) -> None:
    deadline = scenario_deadline()
    token = uuid4().hex
    title = f"NamiSync Test {token}"
    data_root = require_absolute_local_test_root(tmp_path / "isolated")
    process = start_headed_process(
        [
            str(headed_installed_wheel.python),
            str(HOST_CHILD),
            "--data-dir",
            str(data_root),
            "--mutex",
            rf"Local\NamiSync.Test.{token}",
            "--title",
            title,
        ],
        cwd=headed_installed_wheel.root,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    try:
        handle = wait_for_window(process, title, deadline=deadline)
        wait_for_accessible_text(
            handle,
            "Ready",
            python=headed_installed_wheel.python,
            deadline=deadline,
        )
        wait_for_accessible_text(
            handle,
            "NamiSync",
            python=headed_installed_wheel.python,
            deadline=deadline,
        )
        close_window(handle)
        completed = wait_for_process(process, deadline=deadline)
        assert completed.returncode == 0, completed.stdout + completed.stderr
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)

    resource_probe = """
import importlib.resources
import json

path = importlib.resources.files("namisync.interfaces.web") / "assets" / "index.html"
print(json.dumps({"path": str(path), "is_file": path.is_file()}))
"""
    completed = run_with_deadline(
        [str(headed_installed_wheel.python), "-c", resource_probe],
        deadline=deadline,
        cwd=headed_installed_wheel.root,
        env=clean_child_environment(),
        capture_output=True,
        text=True,
        check=True,
    )
    resolved = json.loads(completed.stdout)
    assert resolved["is_file"] is True
    assert Path(resolved["path"]).is_relative_to(headed_installed_wheel.root)
    log_text = read_text(
        data_root / "logs" / "namisync.log",
        deadline=deadline,
    )
    assert "startup.renderer browser_version=" in log_text


def test_sh_g_2_headed_data_root_is_physically_isolated(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path: Path,
) -> None:
    deadline = scenario_deadline()
    data_root = require_absolute_local_test_root(tmp_path / "isolated")
    real_root = Path(os.environ["LOCALAPPDATA"]) / "NamiSync"
    before_real = directory_snapshot(real_root, deadline=deadline)
    process, title, _mutex = _start_injected_host(
        headed_installed_wheel,
        data_root,
        deadline=deadline,
    )
    try:
        handle = wait_for_window(process, title, deadline=deadline)
        wait_for_accessible_text(
            handle,
            "Ready",
            python=headed_installed_wheel.python,
            deadline=deadline,
        )
        close_window(handle)
        completed = wait_for_process(process, deadline=deadline)
        assert completed.returncode == 0, completed.stdout + completed.stderr
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)

    assert directory_snapshot(real_root, deadline=deadline) == before_real
    assert (data_root / "ledger.db").is_file()
    assert (data_root / "history.db").is_file()
    assert (data_root / "logs" / "namisync.log").is_file()

    paths_probe = """
import json
import sys
from namisync.interfaces.web.paths import AppPaths

paths = AppPaths.from_root(sys.argv[1])
print(json.dumps({
    name: str(getattr(paths, name))
    for name in (
        "root", "ledger", "history", "settings", "ui_state",
        "logs", "log_file", "webview2"
    )
}))
"""
    completed = run_with_deadline(
        [str(headed_installed_wheel.python), "-c", paths_probe, str(data_root)],
        deadline=deadline,
        cwd=headed_installed_wheel.root,
        env=clean_child_environment(),
        capture_output=True,
        text=True,
        check=True,
    )
    paths = {name: Path(value) for name, value in json.loads(completed.stdout).items()}
    assert paths["root"] == data_root.resolve()
    assert all(
        path == paths["root"] or path.is_relative_to(paths["root"])
        for path in paths.values()
    )


def test_sh_g_2_relative_data_root_is_refused_before_creation(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path: Path,
) -> None:
    """Deliberately parse one relative root behind an isolated OS boundary."""

    deadline = scenario_deadline()
    relative = Path("relative-gui-data")
    assert not relative.is_absolute()
    token = uuid4().hex
    evidence = _new_evidence_paths(tmp_path / "gui-argument-evidence")
    existing_dialogs = window_handles("NamiSync - Startup Error")
    process = start_headed_process(
        [
            str(headed_installed_wheel.python),
            str(HOST_CHILD),
            "--gui-argument-probe",
            "--value",
            str(relative),
            "--test-mutex",
            rf"Local\NamiSync.Test.{token}",
            "--evidence-dir",
            str(evidence.root),
        ],
        cwd=tmp_path,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    try:
        dialog, message = wait_for_dialog_text(
            process,
            "NamiSync - Startup Error",
            exclude=existing_dialogs,
            deadline=deadline,
        )
        assert "absolute local path" in message
        dismiss_ok_dialog(dialog)
        completed = wait_for_process(process, deadline=deadline)
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)

    assert completed.returncode == 2, completed.stdout + completed.stderr
    assert completed.stdout == completed.stderr == ""
    assert not (tmp_path / relative).exists()
    reader = EvidenceReader(evidence)
    assert reader.available_initial() is None
    assert reader.read_final() is None
    reader.assert_consistent(require_final=False)
    assert list(evidence.root.iterdir()) == []


def test_sh_g_5_database_contract_refusal_is_visible_and_read_only(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path: Path,
) -> None:
    deadline = scenario_deadline()
    data_root = require_absolute_local_test_root(tmp_path / "isolated")
    data_root.mkdir()
    inject_mismatch = """
import sqlite3
import sys
from pathlib import Path
from namisync.workflows.database_pair import initialize_database_pair

root = Path(sys.argv[1])
contract = initialize_database_pair(root / "ledger.db", root / "history.db")
assert contract.state == "ready"
with sqlite3.connect(root / "history.db") as connection:
    connection.execute(
        "UPDATE schema_metadata SET value = ? WHERE key = 'contract_id'",
        ("mismatched-headed-test-contract",),
    )
    connection.commit()
"""
    run_with_deadline(
        [
            str(headed_installed_wheel.python),
            "-c",
            inject_mismatch,
            str(data_root),
        ],
        deadline=deadline,
        cwd=headed_installed_wheel.root,
        env=clean_child_environment(),
        capture_output=True,
        text=True,
        check=True,
    )
    before = _database_bytes(data_root, deadline=deadline)
    token = uuid4().hex
    existing_dialogs = window_handles("NamiSync - Startup Error")
    process = start_headed_process(
        [
            str(headed_installed_wheel.python),
            str(HOST_CHILD),
            "--data-dir",
            str(data_root),
            "--mutex",
            rf"Local\NamiSync.Test.{token}",
            "--title",
            f"NamiSync Test {token}",
        ],
        cwd=headed_installed_wheel.root,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    try:
        dialog, message = wait_for_dialog_text(
            process,
            "NamiSync - Startup Error",
            exclude=existing_dialogs,
            deadline=deadline,
        )
        assert "database pair refused (history-contract)" in message
        guidance = message.casefold()
        for fragment in (
            "close every namisync process",
            "archive or delete both database main files",
            "sidecars together",
            "restart",
        ):
            assert fragment in guidance
        assert all(suffix in message for suffix in ("-wal", "-shm", "-journal"))
        dismiss_ok_dialog(dialog)
        completed = wait_for_process(process, deadline=deadline)
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert completed.stdout == completed.stderr == ""
    assert _database_bytes(data_root, deadline=deadline) == before


def test_sh_g_10_distinct_injected_headed_identities_coexist(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path: Path,
) -> None:
    deadline = scenario_deadline()
    first = _start_injected_host(
        headed_installed_wheel,
        require_absolute_local_test_root(tmp_path / "first"),
        deadline=deadline,
    )
    second = _start_injected_host(
        headed_installed_wheel,
        require_absolute_local_test_root(tmp_path / "second"),
        deadline=deadline,
    )
    processes = (first[0], second[0])
    try:
        first_handle = wait_for_window(first[0], first[1], deadline=deadline)
        second_handle = wait_for_window(second[0], second[1], deadline=deadline)
        wait_for_accessible_text(
            first_handle,
            "Ready",
            python=headed_installed_wheel.python,
            deadline=deadline,
        )
        wait_for_accessible_text(
            second_handle,
            "Ready",
            python=headed_installed_wheel.python,
            deadline=deadline,
        )
        assert first[0].poll() is None
        assert second[0].poll() is None
        close_window(first_handle)
        close_window(second_handle)
        for process in processes:
            completed = wait_for_process(process, deadline=deadline)
            assert completed.returncode == 0, completed.stdout + completed.stderr
    finally:
        for process in processes:
            if process.poll() is None:
                terminate_process_tree(process, deadline=deadline)


def test_br_g_31_second_injected_launch_uses_real_native_activation(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path: Path,
) -> None:
    """Exercise real user32 activation only against a unique test window."""

    deadline = scenario_deadline()
    token = uuid4().hex
    title = f"NamiSync Test {token}"
    mutex = rf"Local\NamiSync.Test.{token}"
    first_process, _, _ = _start_injected_host(
        headed_installed_wheel,
        require_absolute_local_test_root(tmp_path / "first"),
        deadline=deadline,
        title=title,
        mutex=mutex,
    )
    second_process: HeadedProcess | None = None
    try:
        first_handle = wait_for_window(first_process, title, deadline=deadline)
        wait_for_accessible_text(
            first_handle,
            "Ready",
            python=headed_installed_wheel.python,
            deadline=deadline,
        )
        existing_dialogs = window_handles("NamiSync - Startup Error")
        second_process, _, _ = _start_injected_host(
            headed_installed_wheel,
            require_absolute_local_test_root(tmp_path / "second"),
            deadline=deadline,
            title=title,
            mutex=mutex,
        )
        completed, dialog = wait_for_exit_or_dialog(
            second_process,
            "NamiSync - Startup Error",
            exclude=existing_dialogs,
            deadline=deadline,
        )
        if dialog is None:
            assert completed is not None
            assert completed.returncode == 0, completed.stdout + completed.stderr
            assert foreground_window_handle() == first_handle
        else:
            assert completed is None
            assert (
                "The existing NamiSync window could not be brought to the foreground."
                in dialog_text(dialog)
            )
            dismiss_ok_dialog(dialog)
            completed = wait_for_process(second_process, deadline=deadline)
            assert completed.returncode == 0, completed.stdout + completed.stderr
        assert first_process.poll() is None
        close_window(first_handle)
        completed = wait_for_process(first_process, deadline=deadline)
        assert completed.returncode == 0, completed.stdout + completed.stderr
    finally:
        for process in (first_process, second_process):
            if process is not None and process.poll() is None:
                terminate_process_tree(process, deadline=deadline)


def test_br_g_31_foreground_refusal_is_visible_and_nonerror(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path: Path,
) -> None:
    """Force only foregrounding to fail after real UUID find/restore calls."""

    deadline = scenario_deadline()
    token = uuid4().hex
    title = f"NamiSync Test {token}"
    mutex = rf"Local\NamiSync.Test.{token}"
    first_process, _, _ = _start_injected_host(
        headed_installed_wheel,
        require_absolute_local_test_root(tmp_path / "first"),
        deadline=deadline,
        title=title,
        mutex=mutex,
    )
    second_process: HeadedProcess | None = None
    evidence = _new_evidence_paths(tmp_path / "activation-failure-evidence")
    try:
        first_handle = wait_for_window(first_process, title, deadline=deadline)
        wait_for_accessible_text(
            first_handle,
            "Ready",
            python=headed_installed_wheel.python,
            deadline=deadline,
        )
        existing_dialogs = window_handles("NamiSync - Startup Error")
        second_process = start_headed_process(
            (
                headed_installed_wheel.python,
                HOST_CHILD,
                "--activation-failure-probe",
                "--data-dir",
                require_absolute_local_test_root(tmp_path / "second"),
                "--mutex",
                mutex,
                "--title",
                title,
                "--evidence-dir",
                evidence.root,
            ),
            cwd=headed_installed_wheel.root,
            environment=clean_child_environment(),
            deadline=deadline,
        )
        dialog, message = wait_for_dialog_text(
            second_process,
            "NamiSync - Startup Error",
            exclude=existing_dialogs,
            deadline=deadline,
        )
        assert (
            "The existing NamiSync window could not be brought to the foreground."
            in message
        )
        dismiss_ok_dialog(dialog)
        completed = wait_for_process(second_process, deadline=deadline)
        assert completed.returncode == 0, completed.stdout + completed.stderr
        reader = EvidenceReader(evidence)
        result = reader.read_final()
        assert result is not None
        assert type(result.get("exit_code")) is int
        assert type(result.get("restore_calls")) is int
        assert type(result.get("foreground_calls")) is int
        assert result == {
            "exit_code": 0,
            "mutex_names": [mutex],
            "find_titles": [title],
            "restore_calls": 1,
            "foreground_calls": 1,
        }
        reader.assert_consistent(require_final=True, allow_final_only=True)
        assert first_process.poll() is None
        close_window(first_handle)
        completed = wait_for_process(first_process, deadline=deadline)
        assert completed.returncode == 0, completed.stdout + completed.stderr
    finally:
        for process in (first_process, second_process):
            if process is not None and process.poll() is None:
                terminate_process_tree(process, deadline=deadline)


def test_sh_g_10_installed_launcher_fixed_identity_and_isolated_collision(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path: Path,
) -> None:
    """Prove launcher composition and collision without touching product identity.

    The installed launcher must pass the fixed production pair to ``run_desktop``.
    At that boundary the helper maps to a unique real mutex and inert activation
    adapter. Thus two installed launcher executions prove collision/admission,
    but intentionally do not prove user32 foregrounding or acquire the production
    mutex in the user's shared desktop session.
    """

    deadline = scenario_deadline()
    token = uuid4().hex
    test_mutex = rf"Local\NamiSync.Test.{token}"
    test_title = f"NamiSync Test {token}"
    first_root = require_absolute_local_test_root(tmp_path / "first")
    second_root = require_absolute_local_test_root(tmp_path / "second")
    first_evidence = _new_evidence_paths(tmp_path / "first-evidence")
    second_evidence = _new_evidence_paths(tmp_path / "second-evidence")
    release = tmp_path / "primary.release"
    first_process = _start_production_identity_probe(
        headed_installed_wheel,
        data_root=first_root,
        test_mutex=test_mutex,
        test_title=test_title,
        evidence=first_evidence,
        release=release,
        deadline=deadline,
    )
    second_process: HeadedProcess | None = None
    first_reader = EvidenceReader(first_evidence)
    second_reader = EvidenceReader(second_evidence)
    try:
        milestone, first_result = wait_for_initial_evidence(
            first_reader,
            first_process,
            deadline=deadline,
        )
        assert milestone == "ready", first_result
        with first_evidence.ready.open("rb") as held_ready:
            second_process = _start_production_identity_probe(
                headed_installed_wheel,
                data_root=second_root,
                test_mutex=test_mutex,
                test_title=test_title,
                evidence=second_evidence,
                release=release,
                deadline=deadline,
            )
            completed = wait_for_process(second_process, deadline=deadline)
            assert completed.returncode == 0, completed.stdout + completed.stderr
            assert first_process.poll() is None
            second_result = second_reader.read_final()
            assert second_result is not None
            for result in (first_result, second_result):
                assert result["launcher_mutex"] == r"Local\NamiSync.Desktop"
                assert result["launcher_title"] == "NamiSync"
                assert result["mutex_names"] == [r"Local\NamiSync.Desktop"]
                assert type(result.get("primary")) is bool
                assert type(result.get("activated")) is bool
                assert result.get("activation_error") is None or type(
                    result.get("activation_error")
                ) is str
                assert type(result.get("restore_calls")) is int
                assert type(result.get("foreground_boundary_calls")) is int
            assert first_result["primary"] is True
            assert first_result["find_titles"] == []
            assert second_result == {
                "launcher_mutex": r"Local\NamiSync.Desktop",
                "launcher_title": "NamiSync",
                "data_root": str(second_root),
                "primary": False,
                "activated": True,
                "activation_error": None,
                "mutex_names": [r"Local\NamiSync.Desktop"],
                "find_titles": ["NamiSync"],
                "restore_calls": 1,
                "foreground_boundary_calls": 1,
            }
            second_reader.assert_consistent(
                require_final=True,
                allow_final_only=True,
            )
            release.touch()
            completed = wait_for_process(first_process, deadline=deadline)
            assert completed.returncode == 0, completed.stdout + completed.stderr
            released = first_reader.read_final()
            assert released is not None
            assert set(released) == {"released"}
            assert released["released"] is True
            assert held_ready.read(1)
        first_reader.assert_consistent(require_final=True)
    finally:
        for process in (first_process, second_process):
            if process is not None and process.poll() is None:
                terminate_process_tree(process, deadline=deadline)


def _pe_subsystem(path: Path, *, deadline: ScenarioDeadline) -> int:
    executable = read_bytes(path, deadline=deadline)
    pe_offset = struct.unpack_from("<I", executable, 0x3C)[0]
    assert executable[pe_offset : pe_offset + 4] == b"PE\x00\x00"
    optional_header = pe_offset + 24
    magic = struct.unpack_from("<H", executable, optional_header)[0]
    assert magic in {0x10B, 0x20B}
    return struct.unpack_from("<H", executable, optional_header + 68)[0]


def _database_bytes(
    root: Path,
    *,
    deadline: ScenarioDeadline,
) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for pattern in ("ledger.db*", "history.db*"):
        deadline.remaining()
        for path in root.glob(pattern):
            deadline.remaining()
            if path.is_file():
                snapshot[path.name] = read_bytes(path, deadline=deadline)
    return snapshot


def _start_injected_host(
    installed: HeadedInstalledWheel,
    data_root: Path,
    *,
    deadline: ScenarioDeadline,
    title: str | None = None,
    mutex: str | None = None,
) -> tuple[HeadedProcess, str, str]:
    token = uuid4().hex
    selected_title = f"NamiSync Test {token}" if title is None else title
    selected_mutex = (
        rf"Local\NamiSync.Test.{token}" if mutex is None else mutex
    )
    command = [
        str(installed.python),
        str(HOST_CHILD),
        "--data-dir",
        str(data_root),
        "--mutex",
        selected_mutex,
        "--title",
        selected_title,
    ]
    process = start_headed_process(
        command,
        cwd=installed.root,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    return process, selected_title, selected_mutex


def _start_production_identity_probe(
    installed: HeadedInstalledWheel,
    *,
    data_root: Path,
    test_mutex: str,
    test_title: str,
    evidence: EvidencePaths,
    release: Path,
    deadline: ScenarioDeadline,
) -> HeadedProcess:
    return start_headed_process(
        (
            installed.python,
            HOST_CHILD,
            "--production-identity-probe",
            "--data-dir",
            data_root,
            "--test-mutex",
            test_mutex,
            "--test-title",
            test_title,
            "--evidence-dir",
            evidence.root,
            "--release",
            release,
            "--hold-timeout",
            str(deadline.remaining()),
        ),
        cwd=installed.root,
        environment=clean_child_environment(),
        deadline=deadline,
    )


def _new_evidence_paths(root: Path) -> EvidencePaths:
    root.mkdir()
    return EvidencePaths(root.resolve())
