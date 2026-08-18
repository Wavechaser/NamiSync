from __future__ import annotations

import json
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import uuid

import pytest


PROJECT_ROOT = Path(__file__).parents[1]
GUI_SCRIPT = PROJECT_ROOT / "tools" / "gui.ps1"
POWERSHELL = shutil.which("pwsh")
WINDOWS_POWERSHELL = shutil.which("powershell")


def _powershell() -> str:
    if POWERSHELL is None:
        pytest.skip("PowerShell 7 is required for this launcher test")
    return POWERSHELL


def _ps_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_powershell(
    tmp_path: Path,
    body: str,
    *,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    harness = tmp_path / "gui-harness.ps1"
    harness.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        f". {_ps_literal(GUI_SCRIPT)}\n"
        f"{body}\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            _powershell(),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(harness),
        ],
        cwd=PROJECT_ROOT,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def _last_json(result: subprocess.CompletedProcess[str]) -> object:
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines, result.stdout + result.stderr
    return json.loads(lines[-1])


def _write_record(path: Path, milestone: str, payload: object) -> None:
    path.write_text(
        json.dumps(
            {
                "milestone": milestone,
                "payload": payload,
                "schema": "namisync-headed-evidence-v1",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def _ready(output: Path, mode: str = "dark") -> None:
    _write_record(
        output / "ready.json",
        "ready",
        {"mode": mode},
    )


def _final(
    output: Path,
    *,
    exit_code: int = 0,
    host_returned: bool = True,
    post_ready_failure: dict[str, str] | None = None,
) -> None:
    payload: dict[str, object] = {
        "exit_code": exit_code,
        "host_returned": host_returned,
    }
    if post_ready_failure is not None:
        payload["post_ready_failure"] = post_ready_failure
    _write_record(output / "final.json", "final", payload)


def test_gui_plan_defaults_to_shell_and_gallery_defaults_to_dark(
    tmp_path: Path,
) -> None:
    local = tmp_path / "Local App Data"
    body = f"""
$repo = {_ps_literal(PROJECT_ROOT)}
$local = {_ps_literal(local)}
$shell = New-NamiGuiPlan -RepositoryRoot $repo -LocalAppDataRoot $local
$implicit = New-NamiGuiPlan -RepositoryRoot $repo -LocalAppDataRoot $local `
    -Kind gallery -OutputToken same
$explicit = New-NamiGuiPlan -RepositoryRoot $repo -LocalAppDataRoot $local `
    -Kind gallery -Mode dark -OutputToken same
$modes = @{{}}
foreach ($name in @('light', 'dark', 'forced', 'reduced')) {{
    $modes[$name] = New-NamiGuiPlan -RepositoryRoot $repo `
        -LocalAppDataRoot $local -Kind gallery -Mode $name -OutputToken same
}}
$groups = [pscustomobject]@{{
    fluent = @(Resolve-NamiGalleryModes fluent)
    all = @(Resolve-NamiGalleryModes all)
}}
$modeValues = @(
    (Get-Command {_ps_literal(GUI_SCRIPT)}).Parameters['Mode'].Attributes |
        Where-Object {{ $_ -is [Management.Automation.ValidateSetAttribute] }} |
        ForEach-Object {{ $_.ValidValues }}
)
[pscustomobject]@{{
    shell = $shell
    implicit_dark = $implicit
    explicit_dark = $explicit
    dark_equal = (($implicit | ConvertTo-Json -Depth 8 -Compress) -eq `
        ($explicit | ConvertTo-Json -Depth 8 -Compress))
    modes = $modes
    groups = $groups
    mode_values = $modeValues
}} | ConvertTo-Json -Depth 8 -Compress
"""
    result = _run_powershell(tmp_path, body)
    value = _last_json(result)

    shell = value["shell"]
    assert shell["Kind"] == "shell"
    assert shell["Mutex"] == r"Local\NamiSync.Development.Desktop"
    assert shell["Mutex"] != r"Local\NamiSync.Desktop"
    assert shell["Title"] == "NamiSync [Development]"
    assert shell["Title"] != "NamiSync"
    assert shell["LauncherMutex"] == (
        r"Local\NamiSync.Development.Launcher.Desktop"
    )
    assert shell["Child"].endswith(
        r"tests\interfaces\web\_headed_host_child.py"
    )
    assert "--mode" not in shell["Arguments"]

    assert value["dark_equal"] is True
    dark = value["implicit_dark"]
    assert dark["Mode"] == "dark"
    assert dark["Arguments"][dark["Arguments"].index("--mode") + 1] == "dark"
    assert dark["Child"].endswith(
        r"tests\interfaces\web\_component_gallery_child.py"
    )
    assert dark["Scenario"].endswith(
        r"tests\assets\component_gallery\gallery.js"
    )
    assert dark["Python"].endswith(r".venv\Scripts\python.exe")

    assert set(value["modes"]) == {"light", "dark", "forced", "reduced"}
    for mode, plan in value["modes"].items():
        assert plan["Mode"] == mode
        assert plan["Arguments"][plan["Arguments"].index("--mode") + 1] == mode
        assert plan["Mutex"].endswith(f".Gallery.{mode}")
        assert plan["LauncherMutex"].endswith(f".Gallery.{mode}")
        assert f"gallery\\{mode}\\data" in plan["Data"]

    assert len({plan["Mutex"] for plan in value["modes"].values()}) == 4
    assert len(
        {plan["LauncherMutex"] for plan in value["modes"].values()}
    ) == 4

    assert value["groups"] == {
        "fluent": ["light", "dark"],
        "all": ["light", "dark", "forced", "reduced"],
    }
    assert set(value["mode_values"]) == {
        "light",
        "dark",
        "forced",
        "reduced",
        "fluent",
        "all",
    }


def test_mode_without_gallery_refuses_before_creating_data(tmp_path: Path) -> None:
    local = tmp_path / "local"
    body = f"""
try {{
    Invoke-NamiGui -SelectedTarget $null -SelectedMode dark `
        -ModeWasExplicit $true -RepositoryRoot {_ps_literal(PROJECT_ROOT)} `
        -LocalAppDataRoot {_ps_literal(local)}
    exit 9
}}
catch {{
    $_.Exception.Message
}}
"""
    result = _run_powershell(tmp_path, body)

    assert "-Mode is valid only after the gallery command" in result.stdout
    assert not local.exists()


def test_invalid_gallery_mode_is_rejected_by_the_closed_grammar() -> None:
    result = subprocess.run(
        [
            _powershell(),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(GUI_SCRIPT),
            "gallery",
            "-Mode",
            "sepia",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "sepia" in result.stderr


def test_gallery_mode_must_use_the_named_parameter() -> None:
    result = subprocess.run(
        [
            _powershell(),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(GUI_SCRIPT),
            "gallery",
            "dark",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "dark" in result.stderr


def test_mode_without_gallery_is_rejected_by_the_script_entrypoint() -> None:
    result = subprocess.run(
        [
            _powershell(),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(GUI_SCRIPT),
            "-Mode",
            "dark",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 2
    assert "-Mode is valid only after the gallery command" in result.stderr


@pytest.mark.parametrize(
    "arguments",
    [
        ["unknown"],
        ["gallery", "extra"],
    ],
)
def test_unknown_command_and_extra_arguments_are_rejected(
    arguments: list[str],
) -> None:
    result = subprocess.run(
        [
            _powershell(),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(GUI_SCRIPT),
            *arguments,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0


@pytest.mark.skipif(
    WINDOWS_POWERSHELL is None,
    reason="Windows PowerShell is unavailable",
)
def test_windows_powershell_refuses_before_running_the_launcher() -> None:
    result = subprocess.run(
        [
            str(WINDOWS_POWERSHELL),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(GUI_SCRIPT),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "7.0" in result.stderr


def test_process_runner_waits_for_the_returned_child(tmp_path: Path) -> None:
    body = """
$child = Join-Path $PSHOME 'pwsh.exe'
$run = Start-NamiGuiProcess -FilePath $child `
    -Arguments @('-NoLogo', '-NoProfile', '-NonInteractive', '-Command', 'exit 7') `
    -WorkingDirectory $PWD
$run | ConvertTo-Json -Compress
"""
    result = _last_json(_run_powershell(tmp_path, body))

    assert result["ProcessId"] > 0
    assert result["ExitCode"] == 7


def test_process_runner_can_start_before_waiting(tmp_path: Path) -> None:
    event_name = rf"Local\NamiSync.Test.GuiStart.{uuid.uuid4().hex}"
    body = f"""
$gate = [Threading.EventWaitHandle]::new(
    $false,
    [Threading.EventResetMode]::ManualReset,
    {_ps_literal(event_name)}
)
$command = @'
$gate = [Threading.EventWaitHandle]::OpenExisting('{event_name}')
try {{
    if (-not $gate.WaitOne(5000)) {{ exit 9 }}
}}
finally {{
    $gate.Dispose()
}}
exit 0
'@
try {{
    $child = Join-Path $PSHOME 'pwsh.exe'
    $process = Start-NamiGuiProcess -FilePath $child `
        -Arguments @('-NoLogo', '-NoProfile', '-NonInteractive', '-Command', $command) `
        -WorkingDirectory {_ps_literal(tmp_path)} -NoWait
    $runningBeforeRelease = -not $process.HasExited
    [void] $gate.Set()
    $run = Wait-NamiGuiProcess $process
    [pscustomobject]@{{
        running_before_release = $runningBeforeRelease
        exit_code = $run.ExitCode
    }} | ConvertTo-Json -Compress
}}
finally {{
    $gate.Dispose()
}}
"""

    value = _last_json(_run_powershell(tmp_path, body))

    assert value == {"running_before_release": True, "exit_code": 0}


def test_process_runner_sanitizes_python_environment(tmp_path: Path) -> None:
    child = tmp_path / "inspect_environment.py"
    result_path = tmp_path / "environment.json"
    child.write_text(
        "import json, os, pathlib\n"
        "pathlib.Path(os.environ['NAMI_GUI_TEST_RESULT']).write_text(\n"
        "    json.dumps({\n"
        "        'pythonpath': os.environ.get('PYTHONPATH'),\n"
        "        'pythonhome': os.environ.get('PYTHONHOME'),\n"
        "        'pythoninspect': os.environ.get('PYTHONINSPECT'),\n"
        "        'pycache': os.environ.get('PYTHONPYCACHEPREFIX'),\n"
        "        'utf8': os.environ.get('PYTHONUTF8'),\n"
        "    }),\n"
        "    encoding='utf-8',\n"
        ")\n",
        encoding="utf-8",
    )
    body = f"""
$env:PYTHONPATH = 'hostile-path'
$env:PYTHONHOME = 'hostile-home'
$env:PYTHONINSPECT = '1'
$env:PYTHONPYCACHEPREFIX = 'hostile-cache'
$env:NAMI_GUI_TEST_RESULT = {_ps_literal(result_path)}
$run = Start-NamiGuiProcess `
    -FilePath {_ps_literal(PROJECT_ROOT / '.venv/Scripts/python.exe')} `
    -Arguments @({_ps_literal(child)}) -WorkingDirectory {_ps_literal(tmp_path)}
$run | ConvertTo-Json -Compress
"""

    run = _last_json(_run_powershell(tmp_path, body))
    environment = json.loads(result_path.read_text(encoding="utf-8"))

    assert run["ExitCode"] == 0
    assert environment == {
        "pythonpath": None,
        "pythonhome": None,
        "pythoninspect": None,
        "pycache": None,
        "utf8": "1",
    }


def test_project_venv_resolves_editable_source_under_isolation(
    tmp_path: Path,
) -> None:
    python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    probe = (
        "import pathlib, sys; import namisync; "
        "root=pathlib.Path(sys.argv[1]).resolve(); "
        "source=pathlib.Path(namisync.__file__).resolve(); "
        "print(source); "
        "raise SystemExit(0 if source.is_relative_to(root) else 3)"
    )

    result = subprocess.run(
        [str(python), "-I", "-c", probe, str(PROJECT_ROOT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert Path(result.stdout.strip()).resolve().is_relative_to(
        PROJECT_ROOT.resolve()
    )


def test_gallery_status_accepts_complete_lifecycle_and_cleans_owned_output(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "output"
    output = parent / "current"
    output.mkdir(parents=True)
    token = "owned-token"
    (output / ".nami-gui-owner").write_text(token, encoding="utf-8")
    sibling = parent / "keep.txt"
    sibling.write_text("keep", encoding="utf-8")
    _ready(output)
    _final(output)
    body = f"""
$status = Get-NamiGalleryStatus -OutputRoot {_ps_literal(output)} -ExitCode 0
Remove-NamiGalleryOutput {_ps_literal(output)} {_ps_literal(token)}
$status | ConvertTo-Json -Compress
"""
    result = _run_powershell(tmp_path, body)
    status = _last_json(result)

    assert status == {
        "Abnormal": False,
        "Summary": (
            "gallery child closed after publishing ready/final diagnostics"
        ),
    }
    assert not output.exists()
    assert sibling.read_text(encoding="utf-8") == "keep"
    assert "Generated gallery cleanup plan:" not in result.stdout
    assert "Removed generated gallery diagnostic:" not in result.stdout
    assert "Generated gallery diagnostics removed." not in result.stdout


def test_gallery_cleanup_forensic_transcript_is_available_with_verbose(
    tmp_path: Path,
) -> None:
    output = tmp_path / "verbose"
    output.mkdir()
    token = "owned-token"
    (output / ".nami-gui-owner").write_text(token, encoding="utf-8")
    _ready(output)
    _final(output)
    body = f"""
$VerbosePreference = 'Continue'
Remove-NamiGalleryOutput {_ps_literal(output)} {_ps_literal(token)}
"""

    result = _run_powershell(tmp_path, body)

    assert "Generated gallery cleanup plan:" in result.stdout
    assert "file:" in result.stdout
    assert "ownership marker:" in result.stdout
    assert "empty directory:" in result.stdout
    assert "Removed generated gallery diagnostic:" in result.stdout
    assert "Removed gallery ownership marker:" in result.stdout
    assert "Removed empty gallery diagnostic root:" in result.stdout
    assert "Generated gallery diagnostics removed." in result.stdout
    assert not output.exists()


def test_gallery_cleanup_refuses_unknown_or_replaced_ownership(
    tmp_path: Path,
) -> None:
    unknown = tmp_path / "unknown"
    unknown.mkdir()
    (unknown / ".nami-gui-owner").write_text("owned", encoding="utf-8")
    _ready(unknown)
    _final(unknown)
    (unknown / "notes.txt").write_text("keep", encoding="utf-8")

    replaced = tmp_path / "replaced"
    replaced.mkdir()
    (replaced / ".nami-gui-owner").write_text("other", encoding="utf-8")
    _ready(replaced)
    _final(replaced)
    body = f"""
$messages = @()
foreach ($case in @(
    @({_ps_literal(unknown)}, 'owned'),
    @({_ps_literal(replaced)}, 'owned')
)) {{
    try {{
        Remove-NamiGalleryOutput $case[0] $case[1]
        exit 9
    }}
    catch {{ $messages += $_.Exception.Message }}
}}
$messages | ConvertTo-Json -Compress
"""

    messages = _last_json(_run_powershell(tmp_path, body))

    assert any("unexpected gallery diagnostics" in item for item in messages)
    assert any("ownership marker" in item for item in messages)
    assert (unknown / "notes.txt").read_text(encoding="utf-8") == "keep"
    assert (unknown / "ready.json").exists()
    assert (replaced / "ready.json").exists()


def test_gallery_cleanup_reports_partial_completion_after_stat_change(
    tmp_path: Path,
) -> None:
    output = tmp_path / "changed"
    output.mkdir()
    token = "owned"
    (output / ".nami-gui-owner").write_text(token, encoding="utf-8")
    _ready(output)
    _final(output)
    body = f"""
$script:originalOwnershipCheck = `
    ${{function:Assert-NamiGalleryOutputOwnership}}
$script:ownershipChecks = 0
function Assert-NamiGalleryOutputOwnership {{
    param($OutputRoot, $OwnerToken)
    & $script:originalOwnershipCheck $OutputRoot $OwnerToken
    $script:ownershipChecks += 1
    if ($script:ownershipChecks -eq 3) {{
        [IO.File]::AppendAllText((Join-Path $OutputRoot 'final.json'), ' ')
    }}
}}
try {{
    Remove-NamiGalleryOutput {_ps_literal(output)} {_ps_literal(token)}
    exit 9
}}
catch {{ $_.Exception.Message }}
"""

    result = _run_powershell(tmp_path, body)

    assert "changed after cleanup inspection" in result.stdout
    assert "Gallery cleanup incomplete" in result.stdout
    assert "Successfully removed:" in result.stdout
    assert "Remaining root: True; remaining marker: True" in result.stdout
    assert not (output / "ready.json").exists()
    assert (output / "final.json").exists()
    assert (output / ".nami-gui-owner").exists()


def test_gallery_status_rejects_failure_malformed_and_incomplete_records(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing"
    missing.mkdir()

    failed = tmp_path / "failed"
    failed.mkdir()
    _write_record(
        failed / "failure.json",
        "failure",
        {"failure": {"stage": "report", "type": "Error"}},
    )
    _final(failed)

    malformed = tmp_path / "malformed"
    malformed.mkdir()
    _ready(malformed)
    (malformed / "final.json").write_text("{}\n", encoding="utf-8")

    late = tmp_path / "late"
    late.mkdir()
    _ready(late)
    _final(
        late,
        post_ready_failure={"stage": "page_setup", "type": "Error"},
    )

    mismatch = tmp_path / "mismatch"
    mismatch.mkdir()
    _ready(mismatch)
    _final(mismatch, exit_code=7, host_returned=False)

    wrong_types = tmp_path / "wrong-types"
    wrong_types.mkdir()
    _ready(wrong_types)
    _write_record(
        wrong_types / "final.json",
        "final",
        {"exit_code": "0", "host_returned": "true"},
    )

    extra_final = tmp_path / "extra-final"
    extra_final.mkdir()
    _ready(extra_final)
    _write_record(
        extra_final / "final.json",
        "final",
        {"exit_code": 0, "host_returned": True, "unowned": "value"},
    )

    wrong_case = tmp_path / "wrong-case"
    wrong_case.mkdir()
    _ready(wrong_case)
    final_value = {
        "milestone": "final",
        "payload": {"exit_code": 0, "host_returned": True},
        "schema": "NAMISYNC-HEADED-EVIDENCE-V1",
    }
    (wrong_case / "final.json").write_text(
        json.dumps(final_value) + "\n",
        encoding="utf-8",
    )

    body = f"""
[pscustomobject]@{{
    missing = Get-NamiGalleryStatus {_ps_literal(missing)} 0
    failed = Get-NamiGalleryStatus {_ps_literal(failed)} 0
    malformed = Get-NamiGalleryStatus {_ps_literal(malformed)} 0
    late = Get-NamiGalleryStatus {_ps_literal(late)} 0
    mismatch = Get-NamiGalleryStatus {_ps_literal(mismatch)} 0
    wrong_types = Get-NamiGalleryStatus {_ps_literal(wrong_types)} 0
    extra_final = Get-NamiGalleryStatus {_ps_literal(extra_final)} 0
    wrong_case = Get-NamiGalleryStatus {_ps_literal(wrong_case)} 0
}} | ConvertTo-Json -Depth 4 -Compress
"""
    value = _last_json(_run_powershell(tmp_path, body))

    assert all(result["Abnormal"] for result in value.values())
    assert "did not publish ready" in value["missing"]["Summary"]
    assert "published failure diagnostics" in value["failed"]["Summary"]
    assert "invalid envelope" in value["malformed"]["Summary"]
    assert "failed after ready" in value["late"]["Summary"]
    assert "did not return normally" in value["mismatch"]["Summary"]
    assert "exit code does not match" in value["mismatch"]["Summary"]
    assert "invalid payload" in value["wrong_types"]["Summary"]
    assert "invalid payload" in value["extra_final"]["Summary"]
    assert "invalid envelope" in value["wrong_case"]["Summary"]


def test_relaunch_choices_are_closed_and_eof_quits(tmp_path: Path) -> None:
    body = """
[pscustomobject]@{
    enter = Resolve-NamiRelaunchChoice ''
    lower = Resolve-NamiRelaunchChoice 'q'
    upper = Resolve-NamiRelaunchChoice 'Q'
    eof = Resolve-NamiRelaunchChoice $null
    other = Resolve-NamiRelaunchChoice 'again'
} | ConvertTo-Json -Compress
"""
    value = _last_json(_run_powershell(tmp_path, body))

    assert value == {
        "enter": "relaunch",
        "lower": "quit",
        "upper": "quit",
        "eof": "quit",
        "other": "invalid",
    }


def test_gallery_loop_announces_paths_and_relaunches_with_fresh_output(
    tmp_path: Path,
) -> None:
    local = tmp_path / "local"
    body = f"""
$script:childCalls = [Collections.Generic.List[object]]::new()
$script:cleanupCalls = [Collections.Generic.List[string]]::new()
$script:answers = [Collections.Generic.Queue[string]]::new()
$script:answers.Enqueue('')
$script:answers.Enqueue('q')
function Start-NamiGuiProcess {{
    param(
        $FilePath,
        [string[]] $Arguments,
        $WorkingDirectory,
        [switch] $Announce,
        [switch] $NoWait
    )
    if (-not $Announce) {{
        return [pscustomobject]@{{ ProcessId = 10; ExitCode = 0 }}
    }}
    $index = [Array]::IndexOf($Arguments, '--evidence-dir')
    [void] $script:childCalls.Add([pscustomobject]@{{
        Arguments = $Arguments
        Output = $Arguments[$index + 1]
    }})
    Write-Host 'MOCK-CHILD-START'
    return [pscustomobject]@{{ ProcessId = 11; ExitCode = 0 }}
}}
function Wait-NamiGuiProcess {{
    param($Process)
    return [pscustomobject]@{{
        ProcessId = $Process.ProcessId
        ExitCode = $Process.ExitCode
    }}
}}
function Test-NamiMutexExists {{ return $false }}
function Enter-NamiLauncherMutex {{ return [pscustomobject]@{{}} }}
function Exit-NamiLauncherMutex {{ param($Mutex) }}
function Get-NamiLogState {{
    return [pscustomobject]@{{ Exists = $false; Length = 0L; Stamp = 0L }}
}}
function Get-NamiGalleryStatus {{
    return [pscustomobject]@{{
        Abnormal = $false
        Summary = 'gallery child closed after publishing diagnostics'
    }}
}}
function Remove-NamiGalleryOutput {{
    param($OutputRoot, $OwnerToken)
    [void] $script:cleanupCalls.Add($OutputRoot)
    Write-Host 'MOCK-CLEANUP'
}}
function Read-Host {{ return $script:answers.Dequeue() }}
$code = Invoke-NamiGui -SelectedTarget gallery -SelectedMode dark `
    -ModeWasExplicit $false -RepositoryRoot {_ps_literal(PROJECT_ROOT)} `
    -LocalAppDataRoot {_ps_literal(local)}
[pscustomobject]@{{
    code = $code
    calls = @($script:childCalls)
    cleanup_calls = @($script:cleanupCalls)
}} |
    ConvertTo-Json -Depth 6 -Compress
"""

    result = _run_powershell(tmp_path, body)
    value = _last_json(result)

    assert value["code"] == 0
    assert len(value["calls"]) == 2
    outputs = [Path(call["Output"]) for call in value["calls"]]
    assert outputs[0] != outputs[1]
    assert all(output.is_dir() for output in outputs)
    assert result.stdout.index("Data:") < result.stdout.index(
        "MOCK-CHILD-START"
    )
    assert result.stdout.count("MOCK-CHILD-START") == 2
    assert result.stdout.count("MOCK-CLEANUP") == 2
    assert result.stdout.count(
        "Exit [dark]: exit code 0; generated diagnostics removed."
    ) == 2
    assert "Exit [dark]: 0" not in result.stdout
    assert "Status [dark]:" not in result.stdout
    assert value["cleanup_calls"] == [str(path) for path in outputs]


@pytest.mark.parametrize(
    ("profile", "expected_modes"),
    [
        ("fluent", ["light", "dark"]),
        ("all", ["light", "dark", "forced", "reduced"]),
    ],
)
def test_grouped_gallery_starts_every_mode_before_waiting(
    tmp_path: Path,
    profile: str,
    expected_modes: list[str],
) -> None:
    local = tmp_path / "local"
    body = f"""
$script:events = [Collections.Generic.List[string]]::new()
$script:acquired = [Collections.Generic.List[string]]::new()
$script:released = [Collections.Generic.List[string]]::new()
$script:checked = [Collections.Generic.List[string]]::new()
$script:cleaned = [Collections.Generic.List[string]]::new()
function Start-NamiGuiProcess {{
    param(
        $FilePath,
        [string[]] $Arguments,
        $WorkingDirectory,
        [switch] $Announce,
        [switch] $NoWait
    )
    if (-not $Announce) {{
        return [pscustomobject]@{{ ProcessId = 10; ExitCode = 0 }}
    }}
    $index = [Array]::IndexOf($Arguments, '--mode')
    $mode = $Arguments[$index + 1]
    [void] $script:events.Add("start-$mode")
    return [pscustomobject]@{{
        ProcessId = 20 + $script:events.Count
        ExitCode = 0
        Mode = $mode
    }}
}}
function Wait-NamiGuiProcess {{
    param($Process)
    [void] $script:events.Add("wait-$($Process.Mode)")
    return [pscustomobject]@{{
        ProcessId = $Process.ProcessId
        ExitCode = $Process.ExitCode
    }}
}}
function Enter-NamiLauncherMutex {{
    param($Name)
    [void] $script:acquired.Add($Name)
    return [pscustomobject]@{{ Name = $Name }}
}}
function Exit-NamiLauncherMutex {{
    param($Mutex)
    [void] $script:released.Add($Mutex.Name)
}}
function Test-NamiMutexExists {{
    param($Name)
    [void] $script:checked.Add($Name)
    return $false
}}
function Get-NamiLogState {{
    return [pscustomobject]@{{ Exists = $false; Length = 0L; Stamp = 0L }}
}}
function Get-NamiGalleryStatus {{
    return [pscustomobject]@{{ Abnormal = $false; Summary = 'complete' }}
}}
function Remove-NamiGalleryOutput {{
    param($OutputRoot, $OwnerToken)
    [void] $script:cleaned.Add($OutputRoot)
}}
function Read-Host {{ return 'q' }}
$code = Invoke-NamiGui -SelectedTarget gallery -SelectedMode {profile} `
    -ModeWasExplicit $true -RepositoryRoot {_ps_literal(PROJECT_ROOT)} `
    -LocalAppDataRoot {_ps_literal(local)}
[pscustomobject]@{{
    code = $code
    events = @($script:events)
    acquired = @($script:acquired)
    released = @($script:released)
    checked = @($script:checked)
    cleaned = @($script:cleaned)
}} | ConvertTo-Json -Depth 5 -Compress
"""

    result = _run_powershell(tmp_path, body)
    value = _last_json(result)

    starts = [f"start-{mode}" for mode in expected_modes]
    waits = [f"wait-{mode}" for mode in expected_modes]
    assert value["code"] == 0
    assert value["events"] == starts + waits
    assert [name.rsplit(".", 1)[-1] for name in value["acquired"]] == (
        expected_modes
    )
    assert value["released"] == list(reversed(value["acquired"]))
    assert [name.rsplit(".", 1)[-1] for name in value["checked"]] == (
        expected_modes
    )
    assert len(value["cleaned"]) == len(expected_modes)
    assert all(Path(path).is_dir() for path in value["cleaned"])
    assert (
        f"Exit [{profile}]: exit code 0 on "
        f"{len(expected_modes)}/{len(expected_modes)}; "
        "generated diagnostics removed."
    ) in result.stdout
    for mode in expected_modes:
        assert f"Exit [{mode}]:" not in result.stdout
        assert f"Status [{mode}]:" not in result.stdout
    assert f"Gallery profile: {profile}" in result.stdout
    for mode in expected_modes:
        assert f"Gallery mode: {mode}" in result.stdout


def test_fluent_refuses_an_existing_dark_gallery_before_starting_light(
    tmp_path: Path,
) -> None:
    local = tmp_path / "local"
    body = f"""
$script:childStarts = 0
$script:released = [Collections.Generic.List[string]]::new()
function Start-NamiGuiProcess {{
    param(
        $FilePath,
        [string[]] $Arguments,
        $WorkingDirectory,
        [switch] $Announce,
        [switch] $NoWait
    )
    if ($Announce) {{ $script:childStarts += 1 }}
    return [pscustomobject]@{{ ProcessId = 10; ExitCode = 0 }}
}}
function Enter-NamiLauncherMutex {{
    param($Name)
    return [pscustomobject]@{{ Name = $Name }}
}}
function Exit-NamiLauncherMutex {{
    param($Mutex)
    [void] $script:released.Add($Mutex.Name)
}}
function Test-NamiMutexExists {{
    param($Name)
    return $Name.EndsWith('.dark', [StringComparison]::Ordinal)
}}
try {{
    Invoke-NamiGui -SelectedTarget gallery -SelectedMode fluent `
        -ModeWasExplicit $true -RepositoryRoot {_ps_literal(PROJECT_ROOT)} `
        -LocalAppDataRoot {_ps_literal(local)}
    exit 9
}}
catch {{
    [pscustomobject]@{{
        message = $_.Exception.Message
        child_starts = $script:childStarts
        released = @($script:released)
    }} | ConvertTo-Json -Depth 4 -Compress
}}
"""

    value = _last_json(_run_powershell(tmp_path, body))

    assert value["child_starts"] == 0
    assert "dark gallery development window is already running" in value["message"]
    assert [name.rsplit(".", 1)[-1] for name in value["released"]] == [
        "dark",
        "light",
    ]
    assert not local.exists()


def test_fluent_releases_light_lock_when_dark_launcher_lock_is_busy(
    tmp_path: Path,
) -> None:
    local = tmp_path / "local"
    body = f"""
$script:childStarts = 0
$script:acquired = [Collections.Generic.List[string]]::new()
$script:released = [Collections.Generic.List[string]]::new()
function Start-NamiGuiProcess {{
    param(
        $FilePath,
        [string[]] $Arguments,
        $WorkingDirectory,
        [switch] $Announce,
        [switch] $NoWait
    )
    if ($Announce) {{ $script:childStarts += 1 }}
    return [pscustomobject]@{{ ProcessId = 10; ExitCode = 0 }}
}}
function Enter-NamiLauncherMutex {{
    param($Name)
    [void] $script:acquired.Add($Name)
    if ($Name.EndsWith('.dark', [StringComparison]::Ordinal)) {{
        throw 'dark launcher busy'
    }}
    return [pscustomobject]@{{ Name = $Name }}
}}
function Exit-NamiLauncherMutex {{
    param($Mutex)
    [void] $script:released.Add($Mutex.Name)
}}
try {{
    Invoke-NamiGui -SelectedTarget gallery -SelectedMode fluent `
        -ModeWasExplicit $true -RepositoryRoot {_ps_literal(PROJECT_ROOT)} `
        -LocalAppDataRoot {_ps_literal(local)}
    exit 9
}}
catch {{
    [pscustomobject]@{{
        message = $_.Exception.Message
        child_starts = $script:childStarts
        acquired = @($script:acquired)
        released = @($script:released)
    }} | ConvertTo-Json -Depth 4 -Compress
}}
"""

    value = _last_json(_run_powershell(tmp_path, body))

    assert value["child_starts"] == 0
    assert value["message"] == "dark launcher busy"
    assert [name.rsplit(".", 1)[-1] for name in value["acquired"]] == [
        "light",
        "dark",
    ]
    assert [name.rsplit(".", 1)[-1] for name in value["released"]] == [
        "light",
    ]
    assert not local.exists()


def test_fluent_waits_for_light_when_dark_process_fails_to_start(
    tmp_path: Path,
) -> None:
    local = tmp_path / "local"
    body = f"""
$script:events = [Collections.Generic.List[string]]::new()
$script:cleaned = [Collections.Generic.List[string]]::new()
$script:tails = [Collections.Generic.List[string]]::new()
function Start-NamiGuiProcess {{
    param(
        $FilePath,
        [string[]] $Arguments,
        $WorkingDirectory,
        [switch] $Announce,
        [switch] $NoWait
    )
    if (-not $Announce) {{
        return [pscustomobject]@{{ ProcessId = 10; ExitCode = 0 }}
    }}
    $index = [Array]::IndexOf($Arguments, '--mode')
    $mode = $Arguments[$index + 1]
    [void] $script:events.Add("start-$mode")
    if ($mode -eq 'dark') {{ throw 'dark start failed' }}
    return [pscustomobject]@{{ ProcessId = 11; ExitCode = 0; Mode = $mode }}
}}
function Wait-NamiGuiProcess {{
    param($Process)
    [void] $script:events.Add("wait-$($Process.Mode)")
    return [pscustomobject]@{{
        ProcessId = $Process.ProcessId
        ExitCode = $Process.ExitCode
    }}
}}
function Enter-NamiLauncherMutex {{
    param($Name)
    return [pscustomobject]@{{ Name = $Name }}
}}
function Exit-NamiLauncherMutex {{ param($Mutex) }}
function Test-NamiMutexExists {{ return $false }}
function Get-NamiLogState {{
    return [pscustomobject]@{{ Exists = $false; Length = 0L; Stamp = 0L }}
}}
function Get-NamiGalleryStatus {{
    return [pscustomobject]@{{ Abnormal = $false; Summary = 'complete' }}
}}
function Remove-NamiGalleryOutput {{
    param($OutputRoot, $OwnerToken)
    [void] $script:cleaned.Add($OutputRoot)
}}
function Show-NamiLogTail {{
    param($Path, $Before)
    [void] $script:tails.Add($Path)
}}
function Read-Host {{ return 'q' }}
$code = Invoke-NamiGui -SelectedTarget gallery -SelectedMode fluent `
    -ModeWasExplicit $true -RepositoryRoot {_ps_literal(PROJECT_ROOT)} `
    -LocalAppDataRoot {_ps_literal(local)}
[pscustomobject]@{{
    code = $code
    events = @($script:events)
    cleaned = @($script:cleaned)
    tails = @($script:tails)
}} | ConvertTo-Json -Depth 4 -Compress
"""

    result = _run_powershell(tmp_path, body)
    value = _last_json(result)

    assert value["code"] == 1
    assert value["events"] == ["start-light", "start-dark", "wait-light"]
    assert len(value["cleaned"]) == 1
    assert "gallery\\light\\output" in value["cleaned"][0]
    assert len(value["tails"]) == 1
    assert "gallery\\dark\\data\\logs" in value["tails"][0]
    assert "child process failed to start: dark start failed" in result.stdout
    dark_output = local / "NamiSync-Development" / "gallery" / "dark" / "output"
    assert any(path.is_dir() for path in dark_output.iterdir())


def test_abnormal_gallery_retains_output_and_shows_log_tail(
    tmp_path: Path,
) -> None:
    local = tmp_path / "local"
    body = f"""
$script:childOutput = $null
$script:tailCalls = 0
$script:cleanupCalls = 0
function Start-NamiGuiProcess {{
    param(
        $FilePath,
        [string[]] $Arguments,
        $WorkingDirectory,
        [switch] $Announce,
        [switch] $NoWait
    )
    if (-not $Announce) {{
        return [pscustomobject]@{{ ProcessId = 10; ExitCode = 0 }}
    }}
    $index = [Array]::IndexOf($Arguments, '--evidence-dir')
    $script:childOutput = $Arguments[$index + 1]
    return [pscustomobject]@{{ ProcessId = 11; ExitCode = 0 }}
}}
function Wait-NamiGuiProcess {{
    param($Process)
    return [pscustomobject]@{{
        ProcessId = $Process.ProcessId
        ExitCode = $Process.ExitCode
    }}
}}
function Test-NamiMutexExists {{ return $false }}
function Enter-NamiLauncherMutex {{ return [pscustomobject]@{{}} }}
function Exit-NamiLauncherMutex {{ param($Mutex) }}
function Get-NamiLogState {{
    return [pscustomobject]@{{ Exists = $false; Length = 0L; Stamp = 0L }}
}}
function Get-NamiGalleryStatus {{
    return [pscustomobject]@{{ Abnormal = $true; Summary = 'missing final' }}
}}
function Show-NamiLogTail {{
    param($Path, $Before)
    $script:tailCalls += 1
    Write-Host 'MOCK-LOG-TAIL'
}}
function Remove-NamiGalleryOutput {{ $script:cleanupCalls += 1 }}
function Read-Host {{ return 'q' }}
$code = Invoke-NamiGui -SelectedTarget gallery -SelectedMode dark `
    -ModeWasExplicit $false -RepositoryRoot {_ps_literal(PROJECT_ROOT)} `
    -LocalAppDataRoot {_ps_literal(local)}
[pscustomobject]@{{
    code = $code
    output = $script:childOutput
    tail_calls = $script:tailCalls
    cleanup_calls = $script:cleanupCalls
}} | ConvertTo-Json -Compress
"""

    result = _run_powershell(tmp_path, body)
    value = _last_json(result)

    assert value["code"] == 1
    assert value["tail_calls"] == 1
    assert value["cleanup_calls"] == 0
    assert Path(value["output"]).is_dir()
    assert "MOCK-LOG-TAIL" in result.stdout
    assert "Exit [dark]: 0" in result.stdout
    assert "Status [dark]: missing final" in result.stdout
    assert "Gallery diagnostics retained at" in result.stdout


def test_gallery_cleanup_failure_keeps_forensic_console_receipts(
    tmp_path: Path,
) -> None:
    local = tmp_path / "local"
    body = f"""
$script:childOutput = $null
function Start-NamiGuiProcess {{
    param(
        $FilePath,
        [string[]] $Arguments,
        $WorkingDirectory,
        [switch] $Announce,
        [switch] $NoWait
    )
    if (-not $Announce) {{
        return [pscustomobject]@{{ ProcessId = 10; ExitCode = 0 }}
    }}
    $index = [Array]::IndexOf($Arguments, '--evidence-dir')
    $script:childOutput = $Arguments[$index + 1]
    return [pscustomobject]@{{ ProcessId = 11; ExitCode = 0 }}
}}
function Wait-NamiGuiProcess {{
    param($Process)
    return [pscustomobject]@{{ ProcessId = 11; ExitCode = 0 }}
}}
function Test-NamiMutexExists {{ return $false }}
function Enter-NamiLauncherMutex {{ return [pscustomobject]@{{}} }}
function Exit-NamiLauncherMutex {{ param($Mutex) }}
function Get-NamiLogState {{
    return [pscustomobject]@{{ Exists = $false; Length = 0L; Stamp = 0L }}
}}
function Get-NamiGalleryStatus {{
    return [pscustomobject]@{{ Abnormal = $false; Summary = 'complete' }}
}}
function Remove-NamiGalleryOutput {{
    Write-Warning 'Gallery cleanup incomplete.'
    Write-Warning 'Successfully removed: ready.json'
    Write-Warning 'Remaining root: True; remaining marker: True'
    throw 'simulated stat drift'
}}
function Read-Host {{ return 'q' }}
$code = Invoke-NamiGui -SelectedTarget gallery -SelectedMode dark `
    -ModeWasExplicit $false -RepositoryRoot {_ps_literal(PROJECT_ROOT)} `
    -LocalAppDataRoot {_ps_literal(local)}
[pscustomobject]@{{ code = $code; output = $script:childOutput }} |
    ConvertTo-Json -Compress
"""

    result = _run_powershell(tmp_path, body)
    value = _last_json(result)

    assert value["code"] == 1
    assert (
        "Exit [dark]: exit code 0; gallery cleanup failed: "
        "simulated stat drift"
    ) in result.stdout
    assert f"Gallery diagnostics retained at {value['output']}" in result.stdout
    assert "Successfully removed: ready.json" in result.stdout
    assert "Remaining root: True; remaining marker: True" in result.stdout
    assert (
        "Exit [dark]: exit code 0; generated diagnostics removed."
        not in result.stdout
    )


def test_log_tail_is_display_only_and_does_not_contaminate_return_values(
    tmp_path: Path,
) -> None:
    log = tmp_path / "namisync.log"
    log.write_text("first\nsecond\n", encoding="utf-8")
    body = f"""
$before = [pscustomobject]@{{ Exists = $false; Length = 0L; Stamp = 0L }}
$result = @(Show-NamiLogTail {_ps_literal(log)} $before)
[pscustomobject]@{{ success_values = $result.Count }} |
    ConvertTo-Json -Compress
"""

    result = _run_powershell(tmp_path, body)

    assert _last_json(result) == {"success_values": 0}
    assert "first" in result.stdout
    assert "second" in result.stdout


def test_prompt_unavailable_is_treated_as_quit(tmp_path: Path) -> None:
    local = tmp_path / "local"
    body = f"""
$script:childCalls = 0
function Start-NamiGuiProcess {{
    param(
        $FilePath,
        [string[]] $Arguments,
        $WorkingDirectory,
        [switch] $Announce,
        [switch] $NoWait
    )
    if ($Announce) {{ $script:childCalls += 1 }}
    return [pscustomobject]@{{ ProcessId = 10; ExitCode = 0 }}
}}
function Wait-NamiGuiProcess {{
    param($Process)
    return [pscustomobject]@{{
        ProcessId = $Process.ProcessId
        ExitCode = $Process.ExitCode
    }}
}}
function Test-NamiMutexExists {{ return $false }}
function Enter-NamiLauncherMutex {{ return [pscustomobject]@{{}} }}
function Exit-NamiLauncherMutex {{ param($Mutex) }}
function Get-NamiLogState {{
    return [pscustomobject]@{{ Exists = $false; Length = 0L; Stamp = 0L }}
}}
function Read-Host {{
    throw [System.Management.Automation.PSInvalidOperationException]::new(
        'prompt unavailable'
    )
}}
$code = Invoke-NamiGui -SelectedTarget $null -SelectedMode dark `
    -ModeWasExplicit $false -RepositoryRoot {_ps_literal(PROJECT_ROOT)} `
    -LocalAppDataRoot {_ps_literal(local)}
[pscustomobject]@{{ code = $code; child_calls = $script:childCalls }} |
    ConvertTo-Json -Compress
"""

    value = _last_json(_run_powershell(tmp_path, body))

    assert value == {"code": 0, "child_calls": 1}


def test_preexisting_child_mutex_refuses_before_starting_a_window(
    tmp_path: Path,
) -> None:
    local = tmp_path / "local"
    body = f"""
$script:childCalls = 0
function Start-NamiGuiProcess {{
    param(
        $FilePath,
        [string[]] $Arguments,
        $WorkingDirectory,
        [switch] $Announce,
        [switch] $NoWait
    )
    if ($Announce) {{ $script:childCalls += 1 }}
    return [pscustomobject]@{{ ProcessId = 10; ExitCode = 0 }}
}}
function Test-NamiMutexExists {{ return $true }}
function Enter-NamiLauncherMutex {{ return [pscustomobject]@{{}} }}
function Exit-NamiLauncherMutex {{ param($Mutex) }}
try {{
    Invoke-NamiGui -SelectedTarget $null -SelectedMode dark `
        -ModeWasExplicit $false -RepositoryRoot {_ps_literal(PROJECT_ROOT)} `
        -LocalAppDataRoot {_ps_literal(local)}
    exit 9
}}
catch {{
    [pscustomobject]@{{
        message = $_.Exception.Message
        child_calls = $script:childCalls
    }} | ConvertTo-Json -Compress
}}
"""

    value = _last_json(_run_powershell(tmp_path, body))

    assert value["child_calls"] == 0
    assert "already running" in value["message"]


def test_preexisting_launcher_mutex_refuses_before_starting_a_window(
    tmp_path: Path,
) -> None:
    powershell = _powershell()
    mutex_name = rf"Local\NamiSync.Test.Launcher.{uuid.uuid4().hex}"
    holder_script = (
        f"$m=[Threading.Mutex]::new($false,'{mutex_name}');"
        "$owned=$m.WaitOne(5000);"
        "if(-not $owned){[Console]::Out.WriteLine('busy');exit 3};"
        "[Console]::Out.WriteLine('ready');"
        "[Console]::In.ReadLine() | Out-Null;"
        "if($owned){$m.ReleaseMutex()};$m.Dispose()"
    )
    holder = subprocess.Popen(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            holder_script,
        ],
        cwd=PROJECT_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    ready_lines: queue.Queue[str] = queue.Queue()
    assert holder.stdout is not None
    reader = threading.Thread(
        target=lambda: ready_lines.put(holder.stdout.readline()),
        daemon=True,
    )
    reader.start()
    try:
        try:
            ready = ready_lines.get(timeout=10).strip()
        except queue.Empty:
            holder.terminate()
            pytest.fail("launcher-mutex holder did not become ready")
        assert ready == "ready"
        body = f"""
try {{
    $handle = Enter-NamiLauncherMutex {_ps_literal(mutex_name)}
    Exit-NamiLauncherMutex $handle
    exit 9
}}
catch {{
    $_.Exception.Message | ConvertTo-Json -Compress
}}
"""
        value = _last_json(_run_powershell(tmp_path, body))
    finally:
        if holder.stdin is not None:
            holder.stdin.write("\n")
            holder.stdin.flush()
        holder.wait(timeout=10)

    assert "another launcher already owns" in value


def test_launcher_waits_only_for_its_process_and_has_no_broad_cleanup() -> None:
    source = GUI_SCRIPT.read_text(encoding="utf-8")

    assert "[Diagnostics.ProcessStartInfo]::new()" in source
    assert "$start.ArgumentList.Add($argument)" in source
    assert "$Process.WaitForExit()" in source
    for forbidden in (
        "Get-Process",
        "Stop-Process",
        "Start-Process",
        "Wait-Process",
        "taskkill",
        "Remove-Item -Recurse",
        "FileSystemWatcher",
        "Register-ObjectEvent",
    ):
        assert forbidden not in source
