"""Corruption controls for the separate thirteen-case M1-8 UI evidence lane."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

import _m1_8_execution_ui_scale as scoped
import _plan_review_scale as plan_scale
from _frontend_test_support import _node_executable


HERE = Path(__file__).parent
REPOSITORY_ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parents[1]))
adapter = importlib.import_module("m1_8_execution_ui_benchmark")
CONTRACT_PATH = HERE / "m1_7_plan_compact_contract.json"
COMPACT_AUTHORITY_PATH = HERE / "m1_7_plan_compact_authority.json"
MEASUREMENTS_PATH = HERE / "m1_7_plan_compact_measurements.json"
def _contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_bytes())


def _compact_authority() -> tuple[dict[str, object], bytes]:
    content = COMPACT_AUTHORITY_PATH.read_bytes()
    return json.loads(content), content


def _wrapper(receipt: dict[str, object]) -> dict[str, object]:
    return {"receipt": receipt, "receipt_sha256": plan_scale.canonical_sha256(receipt)}


def _fixture(metric_id: str, start: int) -> dict[str, object]:
    rows = []
    specification = _contract()["headed_fixture"]
    metric = next(row for row in _contract()["metrics"] if row["id"] == metric_id)
    count = specification["fresh_execution_plan_count"][metric["sample_kind"]] if metric_id in specification["fresh_execution_metric_ids"] else 1
    for ordinal in range(count):
        value = start + ordinal
        request_id = f"{value:032x}"
        task_id = f"task-{value + 100:032x}"
        session_id = f"{value + 200:032x}"
        source_path = rf"C:\scope\{metric_id}\{value}\source"
        target_path = rf"D:\scope\{metric_id}\{value}\target"
        rows.append({
            "execution_unused": True,
            "initial_view_settlement": {
                "first_row": {
                    "blocked_reason": None,
                    "dependency_count": 0,
                    "depth": 0,
                    "display": "Previous paths",
                    "execution": None,
                    "expanded": True,
                    "first_child_visible_index": 1,
                    "highlighted": False,
                    "is_container": True,
                    "move_peer_id": None,
                    "mtime_ns": None,
                    "node_id": scoped._prior_group_node_id(request_id),
                    "notice": None,
                    "operation_count": 0,
                    "operation_id": None,
                    "operation_kind": None,
                    "parent_visible_index": None,
                    "position_in_set": 1,
                    "reason": None,
                    "risk": "none",
                    "row_kind": "prior-group",
                    "selectable_operation_count": 0,
                    "selected_operation_count": 0,
                    "selection": "disabled",
                    "selection_exclusion_reason": None,
                    "set_size": 19937,
                    "size": None,
                    "visible_index": 0,
                },
                "open_disposition": "opened",
                "plan_session_id": session_id,
                "projection_node_count": 120000,
                "request_id": request_id,
                "source_path": source_path,
                "target_path": target_path,
                "task_id": task_id,
                "view_revision": 0,
                "window_disposition": "current",
                "window_limit": 256,
                "window_offset": 0,
                "window_row_count": 256,
                "window_total": 119999,
                "window_view_revision": 0,
            },
            "plan_session_id": session_id,
            "request_id": request_id,
            "session_released": True,
            "session_state": "completed",
            "source_path": source_path,
            "target_path": target_path,
            "task_id": task_id,
            "task_kind": "sync-plan",
        })
    return {"published_plan_count": count, "rows": rows}


def _readiness_receipt(
    metric_id: str, correctness: object, headed_runtime: object, identity: int
) -> dict[str, object]:
    fixture = _fixture(metric_id, identity * 100)
    return {
        "child_id": f"{identity:032x}",
        "correctness": {metric_id: _u_sample_correctness(metric_id, correctness, fixture, 1)},
        "headed_fixture": fixture,
        "headed_runtime": headed_runtime,
        "launch_token": f"{identity + 10000:032x}",
        "metric_ids": [metric_id],
        "process_identity": {
            "creation_filetime_100ns": identity + 10_000,
            "pid": identity + 1_000,
        },
        "schema": plan_scale.READINESS_CHILD_SCHEMA,
        "surface": "installed-headed",
    }


def _u_sample_correctness(
    metric_id: str, correctness: object, fixture: dict[str, object], iteration: int,
) -> dict[str, object]:
    result = dict(correctness)
    if metric_id in scoped.METRIC_IDS[:8] and metric_id != scoped.METRIC_IDS[2]:
        result.pop("pending_frame", None)
        result.pop("busy_frame", None)
        result.update(feedback_frame=True, frame_outcome="pending")
    if metric_id in scoped.METRIC_IDS[10:]:
        row = fixture["rows"][iteration]
        before, after = {
            "pause": ("running", "pausing"),
            "resume": ("paused", "pending"),
            "cancel": ("running", "canceling"),
        }[result["action"]]
        result.update(
            task_id=row["task_id"],
            session_id=f"{int(row['plan_session_id'], 16) + 500000:032x}",
            expected_session_id=f"{int(row['plan_session_id'], 16) + 500000:032x}",
            code="accepted", before=before, after=after,
        )
    return result


def _authority(
    contract: dict[str, object], compact_authority: dict[str, object], compact_authority_bytes: bytes
) -> tuple[dict[str, object], bytes]:
    source_files = {
        path: {"git_blob_oid": f"{ordinal:040x}", "sha256": f"{ordinal:064x}"}
        for ordinal, path in enumerate(
            (*scoped.SOURCE_ONLY_PATHS, *scoped.PRODUCT_PATHS), start=1
        )
    }
    authority = {
        "compact_authority": compact_authority,
        "compact_authority_receipt": {
            "byte_length": len(compact_authority_bytes),
            "git_blob_oid": plan_scale.git_blob_oid(compact_authority_bytes),
            "sha256": hashlib.sha256(compact_authority_bytes).hexdigest(),
        },
        "contract_sha256": plan_scale.canonical_sha256(contract),
        "product_files": {
            path: {
                "installed_sha256": f"{ordinal + 20:064x}",
                "source_sha256": source_files[path]["sha256"],
                "wheel_member_sha256": f"{ordinal + 30:064x}",
            }
            for ordinal, path in enumerate(scoped.PRODUCT_PATHS, start=1)
        },
        "schema": scoped.AUTHORITY_SCHEMA,
        "source_files": source_files,
    }
    return authority, json.dumps(authority, sort_keys=True, separators=(",", ":")).encode()


def _evidence() -> tuple[
    dict[str, object], dict[str, object], bytes, dict[str, object], bytes, dict[str, object]
]:
    contract = _contract()
    compact_authority, compact_authority_bytes = _compact_authority()
    authority, authority_bytes = _authority(
        contract, compact_authority, compact_authority_bytes
    )
    raw = json.loads(MEASUREMENTS_PATH.read_bytes())
    children = []
    for ordinal, wrapper in enumerate(
        (item for item in raw["children"] if item["receipt"]["metric_id"] in scoped.METRIC_IDS),
        start=1,
    ):
        receipt = deepcopy(wrapper["receipt"])
        receipt["headed_fixture"] = _fixture(receipt["metric_id"], 50_000 + ordinal * 100)
        for iteration, sample in enumerate(receipt["samples"], start=1):
            sample["correctness"] = _u_sample_correctness(
                receipt["metric_id"], sample["correctness"],
                receipt["headed_fixture"], iteration,
            )
        children.append(_wrapper(receipt))
    metrics = {metric["id"]: metric for metric in contract["metrics"]}
    readiness = [
        _wrapper(_readiness_receipt(
            metric_id, metrics[metric_id]["correctness"], compact_authority["headed_runtime"],
            ordinal,
        ))
        for ordinal, metric_id in enumerate(scoped.METRIC_IDS, start=1)
    ]
    receipts = {
        "authority_receipt": {
            "byte_length": len(authority_bytes),
            "git_blob_oid": plan_scale.git_blob_oid(authority_bytes),
            "sha256": hashlib.sha256(authority_bytes).hexdigest(),
        },
        "children": children,
        "collection": _collection(readiness, children),
        "failures": [],
        "readiness": readiness,
        "schema": scoped.RECEIPTS_SCHEMA,
    }
    return contract, compact_authority, compact_authority_bytes, authority, authority_bytes, receipts


def _validate(
    contract: dict[str, object], compact_authority: dict[str, object],
    compact_authority_bytes: bytes, authority: dict[str, object], authority_bytes: bytes,
    receipts: dict[str, object],
) -> tuple[plan_scale.MetricObservation, ...]:
    return scoped.validate_receipts(
        contract, compact_authority, compact_authority_bytes, plan_scale.git_blob_oid(compact_authority_bytes),
        authority, authority_bytes, plan_scale.git_blob_oid(authority_bytes), receipts,
    )


def _rehash(wrapper: dict[str, object]) -> None:
    wrapper["receipt_sha256"] = plan_scale.canonical_sha256(wrapper["receipt"])


def _collection(readiness: list[dict[str, object]], children: list[dict[str, object]]) -> dict[str, object]:
    wrappers = [*readiness, *children]
    planned = []
    accepted = []
    for attempt, wrapper in enumerate(wrappers, start=1):
        receipt = wrapper["receipt"]
        stage = "readiness" if attempt <= len(scoped.METRIC_IDS) else "measurement"
        metric_id = receipt["metric_ids"][0] if stage == "readiness" else receipt["metric_id"]
        planned.append({"attempt": attempt, "launch_token": receipt["launch_token"], "metric_id": metric_id, "stage": stage})
        accepted.append({
            "attempt": attempt, "child_id": receipt["child_id"], "launch_token": receipt["launch_token"],
            "metric_id": metric_id, "process_identity": receipt["process_identity"],
            "receipt_path": f"children/{attempt:02d}.json",
            "receipt_sha256": hashlib.sha256(plan_scale.canonical_json_bytes(receipt)).hexdigest(),
            "stage": stage,
        })
    return {"accepted": accepted, "planned": planned, "state": {"status": "complete"}}


def _reindex(raw: dict[str, object]) -> None:
    raw["collection"] = _collection(raw["readiness"], raw["children"])


def _live_supplemental_workspace(tmp_path: Path) -> dict[str, object]:
    """Build only the supplementary wheel/install inputs from live source bytes."""

    contract = _contract()
    compact, compact_bytes = _compact_authority()
    source_files: dict[str, dict[str, str]] = {}
    for relative in (*scoped.SOURCE_ONLY_PATHS, *scoped.PRODUCT_PATHS):
        content = (REPOSITORY_ROOT / relative).read_bytes()
        source_files[relative] = {
            "git_blob_oid": plan_scale._git_filtered_blob_oid(
                REPOSITORY_ROOT, relative, content,
            ),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    installed_root = tmp_path / "installed"
    wheel_path = tmp_path / "namisync-supplemental.whl"
    product_files: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        for relative in scoped.PRODUCT_PATHS:
            content = (REPOSITORY_ROOT / relative).read_bytes()
            wheel.writestr(relative, content)
            installed_path = installed_root / relative
            installed_path.parent.mkdir(parents=True, exist_ok=True)
            installed_path.write_bytes(content)
            digest = hashlib.sha256(content).hexdigest()
            product_files[relative] = {
                "installed_sha256": digest,
                "source_sha256": digest,
                "wheel_member_sha256": digest,
            }
    authority = {
        "compact_authority": compact,
        "compact_authority_receipt": {
            "byte_length": len(compact_bytes),
            "git_blob_oid": plan_scale.git_blob_oid(compact_bytes),
            "sha256": hashlib.sha256(compact_bytes).hexdigest(),
        },
        "contract_sha256": plan_scale.canonical_sha256(contract),
        "product_files": product_files,
        "schema": scoped.AUTHORITY_SCHEMA,
        "source_files": source_files,
    }
    return {
        "authority": authority,
        "compact": compact,
        "compact_bytes": compact_bytes,
        "contract": contract,
        "installed_root": installed_root,
        "wheel_path": wheel_path,
    }


def _rewrite_live_supplemental_wheel(wheel_path: Path, corrupt_path: str) -> None:
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        for relative in scoped.PRODUCT_PATHS:
            content = (
                b"corrupt supplemental wheel member"
                if relative == corrupt_path
                else (REPOSITORY_ROOT / relative).read_bytes()
            )
            wheel.writestr(relative, content)


def _committed_provenance_repository(
    tmp_path: Path, *, raw_authority_oid: str | None = None, commit: bool = True,
) -> dict[str, object]:
    """Create a clean Git repository carrying the validator's minimal inputs."""

    source_path = "compact-source.py"
    supplemental_path = scoped.SOURCE_ONLY_PATHS[0]
    authority_path = tmp_path / "m1_8_execution_ui_authority.json"
    receipts_path = tmp_path / "m1_8_execution_ui_receipts.json"
    result_path = tmp_path / "m1_8_execution_ui_result.json"
    contents = {source_path: b"compact source\n"}
    contents.update({path: f"source: {path}\n".encode() for path in (*scoped.SOURCE_ONLY_PATHS, *scoped.PRODUCT_PATHS)})
    for relative, content in contents.items():
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_bytes(content)

    def record(relative: str) -> dict[str, str]:
        content = contents[relative]
        return {
            "git_blob_oid": plan_scale.git_blob_oid(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    compact = {"source_files": {source_path: record(source_path)}}
    authority = {
        "compact_authority": compact,
        "source_files": {path: record(path) for path in contents if path != source_path},
    }
    authority_bytes = plan_scale.canonical_json_bytes(authority)
    authority_path.write_bytes(authority_bytes)
    receipts_path.write_bytes(plan_scale.canonical_json_bytes({
        "authority_receipt": {
            "byte_length": len(authority_bytes),
            "git_blob_oid": raw_authority_oid or plan_scale.git_blob_oid(authority_bytes),
            "sha256": hashlib.sha256(authority_bytes).hexdigest(),
        },
    }))
    result_path.write_bytes(b"{}")
    commands = [
        ("git", "init", "--quiet"),
        ("git", "config", "user.email", "m1-8@example.invalid"),
        ("git", "config", "user.name", "M1-8 controls"),
        ("git", "add", "--all"),
    ]
    if commit:
        commands.append(("git", "commit", "--quiet", "-m", "receipt provenance fixture"))
    for command in commands:
        subprocess.run(command, cwd=tmp_path, check=True, capture_output=True, text=True)
    return {
        "authority": authority,
        "authority_path": authority_path,
        "compact": compact,
        "receipts_path": receipts_path,
        "result_path": result_path,
        "supplemental_path": supplemental_path,
    }


def test_scoped_execution_ui_evidence_accepts_exact_thirteen_metric_population() -> None:
    evidence = _evidence()
    observations = _validate(*evidence)

    assert [observation.metric_id for observation in observations] == list(scoped.METRIC_IDS)
    assert [observation.budget for observation in observations] == [50_000_000] * 8 + [100_000_000] * 5
    assert len(evidence[-1]["collection"]["planned"]) == 78
    result = scoped.derive_result(
        json.dumps(evidence[-1], sort_keys=True, separators=(",", ":")).encode(), observations
    )
    scoped.validate_result(
        json.dumps(evidence[-1], sort_keys=True, separators=(",", ":")).encode(), observations, result
    )
    assert "passed" not in evidence[-1]


def test_scoped_execution_ui_rejects_missing_or_reused_child_and_sample() -> None:
    evidence = _evidence()
    missing = deepcopy(evidence[-1])
    missing["children"].pop()
    with pytest.raises(ValueError, match="child membership"):
        _validate(*evidence[:-1], missing)

    reused = deepcopy(evidence[-1])
    first = reused["children"][0]["receipt"]
    second = reused["children"][1]["receipt"]
    second["child_id"] = first["child_id"]
    _rehash(reused["children"][1])
    with pytest.raises(ValueError, match="identity.*reused"):
        _validate(*evidence[:-1], reused)

    duplicate_sample = deepcopy(evidence[-1])
    sample_receipt = duplicate_sample["children"][40]["receipt"]
    sample_receipt["samples"][1] = deepcopy(sample_receipt["samples"][0])
    _rehash(duplicate_sample["children"][40])
    with pytest.raises(ValueError, match="correctness receipt"):
        _validate(*evidence[:-1], duplicate_sample)


def test_scoped_execution_ui_rejects_wrong_runtime() -> None:
    evidence = _evidence()
    changed = deepcopy(evidence[-1])
    changed["children"][0]["receipt"]["headed_runtime"] = {}
    _rehash(changed["children"][0])
    with pytest.raises(ValueError, match="contract is invalid"):
        _validate(*evidence[:-1], changed)


def test_scoped_execution_ui_rejects_hash_and_provenance_corruption() -> None:
    evidence = _evidence()
    corrupt_hash = deepcopy(evidence[-1])
    corrupt_hash["children"][0]["receipt_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="wrapper digest"):
        _validate(*evidence[:-1], corrupt_hash)

    corrupt_provenance = deepcopy(evidence[-1])
    corrupt_provenance["authority_receipt"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="receipt authority"):
        _validate(*evidence[:-1], corrupt_provenance)

@pytest.mark.parametrize(
    "corruption",
    ("wrong-prior-id", "wrong-public-total"),
)
def test_scoped_execution_ui_rejects_rootless_settlement_corruption(corruption: str) -> None:
    evidence = _evidence()
    raw = deepcopy(evidence[-1])
    settlement = raw["readiness"][0]["receipt"]["headed_fixture"]["rows"][0]["initial_view_settlement"]
    first_row = settlement["first_row"]
    if corruption == "wrong-prior-id":
        first_row["node_id"] = "node-" + "0" * 32
    else:
        settlement["window_total"] = 120_000
    _rehash(raw["readiness"][0])

    with pytest.raises(ValueError, match="rootless headed fixture settlement"):
        _validate(*evidence[:-1], raw)


@pytest.mark.parametrize(
    ("corruption", "message"),
    (
        ("source", "supplemental source bytes"),
        ("wheel", "supplemental product bytes"),
        ("installed", "supplemental product bytes"),
    ),
)
def test_scoped_workspace_binds_live_supplemental_source_wheel_and_installed_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str, message: str,
) -> None:
    workspace = _live_supplemental_workspace(tmp_path)
    parent_calls: list[tuple[object, ...]] = []

    def isolate_historical_parent(*args: object) -> None:
        parent_calls.append(args)

    monkeypatch.setattr(
        scoped.plan_scale, "validate_authority_workspace", isolate_historical_parent,
    )

    def validate() -> None:
        scoped.validate_authority_workspace(
            workspace["contract"], workspace["compact"], workspace["compact_bytes"],
            plan_scale.git_blob_oid(workspace["compact_bytes"]), workspace["authority"],
            REPOSITORY_ROOT, workspace["installed_root"], workspace["wheel_path"],
        )

    validate()
    assert len(parent_calls) == 1
    if corruption == "source":
        workspace["authority"]["source_files"][scoped.SOURCE_ONLY_PATHS[0]]["sha256"] = "0" * 64
    elif corruption == "wheel":
        _rewrite_live_supplemental_wheel(workspace["wheel_path"], scoped.PRODUCT_PATHS[0])
    else:
        (workspace["installed_root"] / scoped.PRODUCT_PATHS[0]).write_bytes(b"corrupt installed member")

    with pytest.raises(ValueError, match=message):
        validate()
    assert len(parent_calls) == 2


def test_scoped_committed_sources_require_clean_head_and_raw_authority_binding(tmp_path: Path) -> None:
    clean_root = tmp_path / "clean"
    clean_root.mkdir()
    clean = _committed_provenance_repository(clean_root)
    scoped.validate_committed_sources(
        clean_root, clean["compact"], clean["authority"],
        authority_path=clean["authority_path"], receipts_path=clean["receipts_path"],
        result_path=clean["result_path"],
    )

    (clean_root / clean["supplemental_path"]).write_bytes(b"dirty supplemental source\n")
    with pytest.raises(ValueError, match="committed source bytes changed"):
        scoped.validate_committed_sources(
            clean_root, clean["compact"], clean["authority"],
            authority_path=clean["authority_path"], receipts_path=clean["receipts_path"],
            result_path=clean["result_path"],
        )

    changed_source_root = tmp_path / "changed-source"
    changed_source_root.mkdir()
    changed_source = _committed_provenance_repository(changed_source_root)
    (changed_source_root / changed_source["supplemental_path"]).write_bytes(
        b"committed replacement source\n"
    )
    subprocess.run(
        ("git", "add", changed_source["supplemental_path"]), cwd=changed_source_root,
        check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ("git", "commit", "--quiet", "-m", "changed source"), cwd=changed_source_root,
        check=True, capture_output=True, text=True,
    )
    with pytest.raises(ValueError, match="committed source identity changed"):
        scoped.validate_committed_sources(
            changed_source_root, changed_source["compact"], changed_source["authority"],
            authority_path=changed_source["authority_path"],
            receipts_path=changed_source["receipts_path"], result_path=changed_source["result_path"],
        )

    wrong_raw_root = tmp_path / "wrong-raw-authority"
    wrong_raw_root.mkdir()
    wrong_raw = _committed_provenance_repository(
        wrong_raw_root, raw_authority_oid="f" * 40,
    )
    with pytest.raises(ValueError, match="committed raw authority binding"):
        scoped.validate_committed_sources(
            wrong_raw_root, wrong_raw["compact"], wrong_raw["authority"],
            authority_path=wrong_raw["authority_path"], receipts_path=wrong_raw["receipts_path"],
            result_path=wrong_raw["result_path"],
        )


def test_scoped_staged_sources_bind_index_worktree_and_raw_authority(tmp_path: Path) -> None:
    root = tmp_path / "staged"
    root.mkdir()
    staged = _committed_provenance_repository(root, commit=False)

    def validate() -> None:
        scoped.validate_staged_sources(
            root, staged["compact"], staged["authority"],
            authority_path=staged["authority_path"], receipts_path=staged["receipts_path"],
            result_path=staged["result_path"],
        )

    validate()
    source_path = root / staged["supplemental_path"]
    source_path.write_bytes(b"unstaged source change\n")
    with pytest.raises(ValueError, match="staged source bytes changed"):
        validate()
    source_path.write_bytes(f"source: {staged['supplemental_path']}\n".encode())

    source_path.write_bytes(b"different staged source\n")
    subprocess.run(("git", "add", staged["supplemental_path"]), cwd=root, check=True, capture_output=True)
    with pytest.raises(ValueError, match="staged source bytes changed"):
        validate()

    source_path.write_bytes(f"source: {staged['supplemental_path']}\n".encode())
    with pytest.raises(ValueError, match="staged source identity changed"):
        validate()
    subprocess.run(("git", "add", staged["supplemental_path"]), cwd=root, check=True, capture_output=True)
    result_path = staged["result_path"]
    result_path.write_bytes(b'{"changed":true}')
    with pytest.raises(ValueError, match="staged evidence bytes changed"):
        validate()

    result_path.write_bytes(b"{}")
    receipts_path = staged["receipts_path"]
    receipts = json.loads(receipts_path.read_bytes())
    receipts["authority_receipt"]["git_blob_oid"] = "f" * 40
    receipts_path.write_bytes(plan_scale.canonical_json_bytes(receipts))
    subprocess.run(("git", "add", str(receipts_path)), cwd=root, check=True, capture_output=True)
    with pytest.raises(ValueError, match="staged raw authority binding"):
        validate()


def test_scoped_execution_ui_retains_first_failure_and_refuses_replacement() -> None:
    evidence = _evidence()
    failed = deepcopy(evidence[-1])
    failed["failures"] = [{
        "error": "headed child timed out after 30 seconds",
        "error_class": "TimeoutExpired",
        "error_truncated": False,
        "exit_code": None,
        "launch_token": "c" * 32,
        "metric_id": scoped.METRIC_IDS[1],
        "raw_log": {"byte_length": 91, "sha256": "d" * 64},
        "stage": "measurement",
        "timed_out": True,
    }]
    with pytest.raises(ValueError, match="stopped on retained failure"):
        _validate(*evidence[:-1], failed)


def test_scoped_execution_ui_rejects_p95_and_maximum_only_breaches() -> None:
    evidence = _evidence()
    p95_breach = deepcopy(evidence[-1])
    for wrapper in p95_breach["children"]:
        if wrapper["receipt"]["metric_id"] == scoped.METRIC_IDS[8]:
            for sample in wrapper["receipt"]["samples"]:
                sample["elapsed_ns"] = 100_000_001
            _rehash(wrapper)
    with pytest.raises(ValueError, match="statistic exceeds"):
        _validate(*evidence[:-1], p95_breach)

    maximum_breach = deepcopy(evidence[-1])
    maximum_breach["children"][40]["receipt"]["samples"][0]["elapsed_ns"] = 250_000_001
    _rehash(maximum_breach["children"][40])
    with pytest.raises(ValueError, match="maximum exceeds"):
        _validate(*evidence[:-1], maximum_breach)


def test_scoped_execution_ui_harmless_variation_changes_retained_observation() -> None:
    evidence = _evidence()
    original = _validate(*evidence)
    varied = deepcopy(evidence[-1])
    for wrapper in varied["children"]:
        if wrapper["receipt"]["metric_id"] == scoped.METRIC_IDS[0]:
            for sample in wrapper["receipt"]["samples"]:
                sample["elapsed_ns"] += 1
            _rehash(wrapper)
    _reindex(varied)
    changed = _validate(*evidence[:-1], varied)

    assert changed[0].statistic == original[0].statistic + 1
    assert changed[0].maximum == original[0].maximum + 1


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda raw: raw["collection"]["planned"].pop(), "collection plan is incomplete"),
        (lambda raw: raw["collection"]["accepted"].reverse(), "collection accepted attempt"),
    ],
)
def test_scoped_execution_ui_rejects_durable_index_corruption(
    mutate: object, message: str,
) -> None:
    evidence = _evidence()
    raw = deepcopy(evidence[-1])
    mutate(raw)
    with pytest.raises(ValueError, match=message):
        _validate(*evidence[:-1], raw)


def test_scoped_adapter_refuses_evidence_overwrite_and_restart(tmp_path: Path) -> None:
    output = tmp_path / "authority.json"
    adapter._write_once(output, {"a": 1})
    with pytest.raises(FileExistsError, match="already exists"):
        adapter._write_once(output, {"a": 2})

    collection_root = tmp_path / "collection"
    collection_root.mkdir()
    (collection_root / "collection.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError, match="collection already exists"):
        adapter.collect(
            python=Path(sys.executable), authority_path=output, output=tmp_path / "receipts.json",
            collection_root=collection_root, contract_path=CONTRACT_PATH,
            benchmark_root=tmp_path, installed_root=tmp_path,
        )


@pytest.mark.parametrize("index_replace_refused", (False, True))
def test_scoped_adapter_persists_first_failure_before_any_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    index_replace_refused: bool,
) -> None:
    evidence = _evidence()
    authority = deepcopy(evidence[3])
    compact_bytes = plan_scale.canonical_json_bytes(authority["compact_authority"])
    authority["compact_authority_receipt"] = {
        "byte_length": len(compact_bytes), "git_blob_oid": plan_scale.git_blob_oid(compact_bytes),
        "sha256": hashlib.sha256(compact_bytes).hexdigest(),
    }
    authority_bytes = plan_scale.canonical_json_bytes(authority)
    authority_path = tmp_path / "authority.json"
    authority_path.write_bytes(authority_bytes)
    collection_root = tmp_path / "collection"
    collection_root.mkdir()
    calls: list[object] = []

    def fail(command: object, **_kwargs: object) -> object:
        calls.append(command)
        raise subprocess.TimeoutExpired(command, 300, output=b"stdout", stderr=b"stderr")

    monkeypatch.setattr(adapter.subprocess, "run", fail)
    if index_replace_refused:
        replace = adapter.os.replace

        def refuse_failed_index(source: Path, destination: Path) -> None:
            if b'"status":"failed"' in Path(source).read_bytes():
                raise PermissionError("failure index replacement refused")
            replace(source, destination)

        monkeypatch.setattr(adapter.os, "replace", refuse_failed_index)
    expected_error = PermissionError if index_replace_refused else RuntimeError
    with pytest.raises(expected_error, match="replacement refused" if index_replace_refused else "first failure"):
        adapter.collect(
            python=Path(sys.executable), authority_path=authority_path,
            output=tmp_path / "receipts.json", collection_root=collection_root,
            contract_path=CONTRACT_PATH, benchmark_root=tmp_path, installed_root=tmp_path,
        )
    index = json.loads((collection_root / "collection.json").read_bytes())
    failed = index["state"]
    assert len(calls) == 1
    assert failed["status"] == ("launching" if index_replace_refused else "failed")
    assert failed["attempt"] == 1
    if not index_replace_refused:
        assert failed["failure"]["timed_out"] is True
        assert failed["failure"]["exit_code"] is None
    packet = json.loads((collection_root / "failed-receipts.json").read_bytes())
    assert packet["failures"][0]["timed_out"] is True
    assert packet["failures"][0]["exit_code"] is None
    assert packet["receipts"] == []
    assert (collection_root / "logs" / "01.log").read_bytes() == b"stdoutstderr"
    if index_replace_refused:
        assert any(b'"status":"failed"' in path.read_bytes() for path in collection_root.glob(".collection.json.*.tmp"))


@pytest.mark.parametrize("metric_id", scoped.METRIC_IDS)
@pytest.mark.parametrize("readiness", (False, True))
def test_ui_script_adapter_changes_scoped_feedback_and_retains_other_endpoints(
    metric_id: str, readiness: bool,
) -> None:
    original = adapter.legacy._headed_probe_script(metric_id, readiness=readiness)
    adapted = adapter._rootless_probe_script(metric_id, readiness=readiness)
    assert original.count("initialWindow.total !== 120000") == 1
    assert adapted != original
    assert adapted.count("initialWindow.total !== 119999") == 1
    assert adapted.count("const uFeedback =") == 1
    assert adapted.count("feedback_frame: true") == 5
    assert adapted.count("uFeedback.controlCorrectness") == 2

    def branch(script: str, start: str, end: str) -> str:
        return script.split(start, 1)[1].split(end, 1)[0]

    assert branch(
        adapted, '  } else if (metric === "ui_start_execution_click_feedback") {',
        '  } else if (metric === "ui_confirm_execution_click_feedback") {',
    ) == branch(
        original, '  } else if (metric === "ui_start_execution_click_feedback") {',
        '  } else if (metric === "ui_confirm_execution_click_feedback") {',
    )
    assert branch(
        adapted, '  } else if (metric === "ui_get_plan_window_one_row_receipt") {',
        '  } else if (metric === "ui_start_execution_receipt") {',
    ) == branch(
        original, '  } else if (metric === "ui_get_plan_window_one_row_receipt") {',
        '  } else if (metric === "ui_start_execution_receipt") {',
    )


def test_ui_generated_script_parses_and_selection_warmup_uses_typed_observer(tmp_path: Path) -> None:
    node = _node_executable()
    assert node is not None, "Node.js is required for the U script seam control"
    script = adapter._rootless_probe_script(scoped.METRIC_IDS[1], readiness=True)
    assert "const warmupObservation = uFeedback.observeDispatch" in script
    assert "await warmupObservation.finish();" in script
    assert "selection_revision === initialSummary.selection_revision + 1" in script
    path = tmp_path / "u-probe.js"
    path.write_text(script, encoding="utf-8")
    completed = subprocess.run(
        (str(node), "--max-old-space-size=128", "--check", str(path)),
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_ui_generated_timed_observer_accepts_both_orders_and_rejects_false_actions() -> None:
    node = _node_executable()
    assert node is not None, "Node.js is required for the U observer control"
    script = adapter._rootless_probe_script(scoped.METRIC_IDS[5])
    start = script.index("  async function timedClick(element, review, pending, observer, settledUI")
    end = script.index("  async function timedReceipt(", start)
    timed_click = script[start:end]
    helper = (REPOSITORY_ROOT / "tests/assets/m1_8_execution_ui_probe.mjs").read_text(encoding="utf-8")
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const [helper, timedClick] = JSON.parse(fs.readFileSync(0, 'utf8'));
const window = {pywebview: {api: null}};
let document;
const nextFrame = () => new Promise((resolve) => setImmediate(resolve));
const until = async (predicate) => {
  for (let i = 0; i < 4; i += 1) {
    if (predicate()) return true;
    await nextFrame();
  }
  throw Error('typed reply missing');
};
const {uFeedback, click} = new Function('window', 'document', 'nextFrame', 'until', 'performance',
  `${helper}\n${timedClick}\nreturn {uFeedback, click: timedClick};`)(
    window, {querySelector: (...args) => document.querySelector(...args)}, nextFrame, until, performance);
const TASK = `task-${'a'.repeat(32)}`;
const SESSION = 'b'.repeat(32);
const REQUEST = 'c'.repeat(32);
const before = {pause: 'running', resume: 'paused', cancel: 'running'};
const after = {pause: 'pausing', resume: 'pending', cancel: 'canceling'};

async function run(kind, order, fault = null) {
  const action = kind.startsWith('control-') ? kind.slice(8) : kind;
  const confirmed = kind === 'confirm';
  const start = kind === 'confirm' || kind === 'execute';
  const pending = start ? 'execute' : kind === 'sort' ? 'view' : kind === 'selection' ? 'selection' : action;
  const row = {task_id: TASK, session_id: SESSION, request_id: REQUEST,
    source_path: 'C:/source', target_path: 'D:/target'};
  const controls = {
    pause: {hidden: false, disabled: false},
    resume: {hidden: true, disabled: true},
    cancel: {hidden: false, disabled: false},
  };
  const sortHeader = {ariaSort: 'none', isConnected: true};
  const selection = {checked: false};
  const source = {textContent: row.source_path};
  const target = {textContent: row.target_path};
  let status = '';
  const review = {
    isConnected: true, dataset: {pending: confirmed ? 'confirmation' : ''},
    querySelector: (selector) => {
      if (selector === '.nami-plan-review__status') return {textContent: status};
      if (selector === '.nami-plan-review__path--source .nami-labeled-path__value') return source;
      if (selector === '.nami-plan-review__path--target .nami-labeled-path__value') return target;
      const control = selector.match(/data-action="([a-z]+)"/);
      return control ? controls[control[1]] : null;
    },
    contains: (element) => element?.parentElement === sortHeader,
  };
  const dialog = {open: confirmed};
  document = {querySelector: (selector) => ({
    '.nami-plan-review': review,
    '#execution-confirmation': dialog,
    '#app': {inert: confirmed},
    '#theme-options': {inert: confirmed},
  })[selector] ?? null};
  let release;
  const native = new Promise((resolve) => {release = resolve;});
  const api = {dispatch: () => native};
  window.pywebview.api = api;
  const request = {
    request_id: 'd'.repeat(32), command: kind === 'sort' ? 'update_plan_view'
      : kind === 'selection' ? 'mutate_plan_selection' : 'control_execution',
    payload: {task_id: TASK, session_id: SESSION, action,
      expected_revision: 1, expected_view_revision: 1,
      expected_selection_revision: 1, sort_column: 'size', sort_direction: 'ascending',
      node_id: 'node', selected: true},
  };
  const result = kind === 'sort'
    ? {disposition: 'applied', task_id: TASK, request_id: REQUEST,
      view_revision: 2, sort_column: 'size', sort_direction: 'ascending'}
    : kind === 'selection'
      ? {disposition: 'applied', task_id: TASK, request_id: REQUEST,
        view_revision: 2, selection_revision: 2}
      : {accepted: true, code: 'accepted', session_id: SESSION,
        before: before[action], after: after[action], detail: 'accepted'};
  const nativeReply = {transport_version: 1, response_token: null,
    response: {schema_version: 1, request_id: request.request_id, ok: true, result}};
  const succeedUI = () => {
    review.dataset.pending = '';
    if (kind === 'sort') {
      sortHeader.ariaSort = 'ascending';
      if (fault === 'detached-header') sortHeader.isConnected = false;
    }
    else if (kind === 'selection') selection.checked = true;
    else if (start) status = 'Execution running.';
    else if (action === 'pause') {
      status = fault === 'advanced-progress' ? 'Execution paused. Resume available.' : 'Pausing execution…';
      controls.pause.disabled = true;
      if (fault === 'advanced-progress') {controls.resume.hidden = false; controls.resume.disabled = false;}
    } else if (action === 'resume') {
      status = fault === 'advanced-progress' ? 'Execution running.' : 'Execution waiting.';
      controls.pause.disabled = fault !== 'advanced-progress';
    } else {
      status = fault === 'advanced-progress' ? 'Execution canceled.' : 'Canceling execution…';
      controls.cancel.disabled = true;
    }
  };
  let observer;
  if (start) {
    let accepted = false;
    observer = {peek: () => accepted, facts: () => ({accepted}),
      finish: async () => {if (!accepted) throw Error('missing start receipt');}};
    release = () => {accepted = fault !== 'refused' && fault !== 'wrong-identity';
      if (fault !== 'wrong-ui') succeedUI();};
  } else {
    observer = kind.startsWith('control-')
      ? uFeedback.observeControl(row, action)
      : uFeedback.observeDispatch(request.command, {
        task_id: TASK,
        matches: (payload) => kind === 'sort'
          ? payload.sort_column === 'size' && payload.expected_revision === 1
          : payload.node_id === 'node' && payload.expected_view_revision === 1
            && payload.expected_selection_revision === 1,
      }, (value) => kind === 'sort'
        ? value?.disposition === 'applied' && value.view_revision === 2
          && value.task_id === TASK && value.request_id === REQUEST
        : value?.disposition === 'applied' && value.selection_revision === 2
          && value.task_id === TASK && value.request_id === REQUEST);
    const nativeRelease = release;
    release = () => {
      if (fault === 'refused') nativeReply.response.result = {...result, accepted: false,
        disposition: 'conflict', code: 'illegal-state'};
      if (fault === 'wrong-identity') nativeReply.response.request_id = 'e'.repeat(32);
      if (fault === 'malformed-envelope') nativeReply.response.schema_version = 9;
      if (fault !== 'wrong-ui') native.then(succeedUI);
      nativeRelease(nativeReply);
    };
  }
  const element = {
    isConnected: fault !== 'detached', disabled: fault === 'disabled', hidden: false,
    closest: () => fault === 'hidden' ? {} : null,
    parentElement: sortHeader,
    click: () => {
      review.dataset.pending = pending;
      if (fault === 'wrong-current-review') source.textContent = 'C:/other';
      status = `${action[0].toUpperCase()}${action.slice(1)} requested…`;
      if (!start && !fault?.startsWith('no-dispatch')) {
        if (fault === 'stale-revision') {
          request.payload.expected_revision = 9;
          request.payload.expected_view_revision = 9;
        }
        if (fault === 'wrong-session') request.payload.session_id = 'e'.repeat(32);
        api.dispatch(JSON.stringify(request));
      }
      if (order === 'before' && fault !== 'no-dispatch') queueMicrotask(release);
    },
  };
  const settled = (frame) => kind === 'sort'
    ? uFeedback.sortSuccessor(row, review, element, frame)
    : kind === 'selection' ? frame.pending === '' && selection.checked === true
        && uFeedback.currentReview(row, review) !== null
      : start ? uFeedback.startedSuccessor(row, frame, confirmed)
        : uFeedback.controlSuccessor(review, row, action, frame);
  const invoke = () => click(element, review, pending, observer, settled,
    confirmed ? 'confirmation' : '', row);
  if (fault === 'wrong-ui' || fault === 'no-dispatch') {
    const feedback = await invoke();
    assert.equal(feedback.outcome, 'pending');
    if (fault === 'no-dispatch') await assert.rejects(observer.finish());
    else {
      await observer.finish();
      assert.equal(settled({pending: review.dataset.pending, connected: true}), false);
    }
    observer.dispose?.();
    return;
  }
  if (fault && fault !== 'no-dispatch-pending' && fault !== 'advanced-progress') {
    await assert.rejects(invoke());
    observer.dispose?.();
    return;
  }
  const feedback = await invoke();
  assert.equal(feedback.outcome, order === 'before' ? 'accepted' : 'pending');
  if (order === 'after') release();
  if (fault === 'no-dispatch-pending') await assert.rejects(observer.finish());
  else await observer.finish();
  observer.dispose?.();
}

(async () => {
  const kinds = ['sort', 'selection', 'confirm', 'execute',
    'control-pause', 'control-resume', 'control-cancel'];
  for (const kind of kinds) {
    await run(kind, 'before');
    await run(kind, 'after');
    for (const fault of ['refused', 'wrong-identity', 'wrong-ui',
      'disabled', 'detached', 'hidden', 'no-dispatch', 'wrong-current-review']) {
      await run(kind, 'before', fault);
    }
    if (kind !== 'confirm' && kind !== 'execute') {
      await run(kind, 'before', 'malformed-envelope');
      if (kind === 'sort' || kind === 'selection') await run(kind, 'before', 'stale-revision');
      if (kind === 'sort') await run(kind, 'before', 'detached-header');
      if (kind.startsWith('control-')) await run(kind, 'before', 'wrong-session');
    }
    if (kind.startsWith('control-')) await run(kind, 'before', 'advanced-progress');
  }
  await run('control-pause', 'after', 'no-dispatch-pending');
})().catch((error) => {console.error(error); process.exitCode = 1;});
"""
    completed = subprocess.run(
        (str(node), "--max-old-space-size=128", "-e", harness),
        input=json.dumps([helper, timed_click]), capture_output=True, text=True,
        timeout=20, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_ui_start_receipt_observer_binds_exact_plan_request_and_removes_listener() -> None:
    node = _node_executable()
    assert node is not None, "Node.js is required for the U start observer control"
    script = adapter._rootless_probe_script(scoped.METRIC_IDS[3])
    start = script.index("  function observeStartReceipt(row) {")
    end = script.index("  async function openExecutionConfirmation(", start)
    observer_source = script[start:end]
    helper = (REPOSITORY_ROOT / "tests/assets/m1_8_execution_ui_probe.mjs").read_text(encoding="utf-8")
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const [helper, source] = JSON.parse(fs.readFileSync(0, 'utf8'));
const listeners = new Set();
globalThis.chrome = {webview: {
  addEventListener: (_kind, callback) => listeners.add(callback),
  removeEventListener: (_kind, callback) => listeners.delete(callback),
}};
const nativeDispatch = (_wire) => Promise.resolve({});
const window = {pywebview: {api: {dispatch: nativeDispatch}}};
const observe = new Function('window', 'performance',
  `${helper}\n${source}; return observeStartReceipt;`)(window, performance);
const row = {task_id: `task-${'a'.repeat(32)}`, request_id: 'b'.repeat(32),
  selection_revision: 1, destructive_operation_count: 1};
const transport = 'c'.repeat(32);
const dispatch = (planId = row.request_id, requestId = transport,
  commandId = 'f'.repeat(32)) => window.pywebview.api.dispatch(JSON.stringify({
  schema_version: 1, request_id: requestId, command: 'start_execution',
  payload: {task_id: row.task_id, request_id: planId, expected_revision: 1,
    destructive_acknowledged: true, command_id: commandId},
}));
const send = (runId, ok = true, requestId = transport) => {
  const event = {data: {
    kind: 'namisync.command-completion.v1', generation: 1,
    phase: 'completion', request_id: requestId, completion_token: 'd'.repeat(32),
    response: {schema_version: 1, request_id: requestId, ok,
      result: {task_id: row.task_id, request_id: runId, session_id: 'e'.repeat(32)}},
  }};
  for (const callback of [...listeners]) callback(event);
};
(async () => {
  const wrong = observe(row);
  wrong.start();
  await dispatch('9'.repeat(32));
  send('1'.repeat(32));
  await assert.rejects(wrong.promise, /typed execution receipt is invalid/);
  assert.equal(listeners.size, 0);
  assert.equal(window.pywebview.api.dispatch, nativeDispatch);
  const refused = observe(row);
  refused.start();
  await dispatch();
  send('1'.repeat(32), false);
  await assert.rejects(refused.promise, /typed execution receipt is invalid/);
  assert.equal(window.pywebview.api.dispatch, nativeDispatch);
  const receipt = observe(row);
  receipt.start();
  await dispatch();
  send('1'.repeat(32), true, '2'.repeat(32));
  assert.equal(receipt.peek(), false);
  assert.equal(listeners.size, 1);
  send('1'.repeat(32));
  const value = await receipt.promise;
  assert.equal(value.value.request_id, '1'.repeat(32));
  assert.notEqual(value.value.request_id, row.request_id);
  assert.equal(receipt.peek(), true);
  assert.deepEqual(receipt.facts().exact, true);
  assert.equal(listeners.size, 0);
  assert.equal(window.pywebview.api.dispatch, nativeDispatch);
  const replay = observe(row);
  replay.start();
  await dispatch();
  await dispatch(row.request_id, '6'.repeat(32));
  send('1'.repeat(32), true, '6'.repeat(32));
  await replay.promise;
  assert.equal(replay.facts().exact, true);
  const independent = observe(row);
  independent.start();
  await dispatch();
  await dispatch(row.request_id, '6'.repeat(32), '7'.repeat(32));
  send('1'.repeat(32), true, '6'.repeat(32));
  await assert.rejects(independent.promise, /typed execution receipt is invalid/);
  assert.equal(window.pywebview.api.dispatch, nativeDispatch);
})().catch((error) => {console.error(error); process.exitCode = 1;});
"""
    completed = subprocess.run(
        (str(node), "--max-old-space-size=128", "-e", harness),
        input=json.dumps([helper, observer_source]), capture_output=True, text=True,
        timeout=20, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_ui_start_settlement_binds_public_plan_and_returned_session() -> None:
    node = _node_executable()
    assert node is not None, "Node.js is required for the U start settlement control"
    script = adapter._rootless_probe_script(scoped.METRIC_IDS[3])
    start = script.index("  async function settleStartedExecution(prepared, observation) {")
    end = script.index("  async function prepareExecutionControl(", start)
    source = script[start:end]
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = JSON.parse(fs.readFileSync(0, 'utf8'));
const TASK = `task-${'a'.repeat(32)}`;
const PLAN = 'b'.repeat(32);
const RUN = 'c'.repeat(32);
const SESSION = 'd'.repeat(32);
const summary = {task_id: TASK, task_kind: 'sync-plan',
  request_id: PLAN, session_id: SESSION};
const bridge = {listTasks: async () => ({tasks: [summary]})};
const until = async (predicate) => {
  if (!predicate()) throw Error('execution admission did not settle');
};
const document = {querySelector: () => ({open: false})};
const settle = new Function('bridge', 'until', 'document',
  `${source}; return settleStartedExecution;`)(bridge, until, document);
const prepared = {row: {task_id: TASK, request_id: PLAN},
  review: {dataset: {pending: ''}, querySelector: () => ({disabled: false})}};
const receipt = {value: {task_id: TASK, request_id: RUN, session_id: SESSION}};
(async () => {
  assert.equal((await settle(prepared, {promise: Promise.resolve(receipt)})).value.request_id, RUN);
  summary.request_id = 'e'.repeat(32);
  await assert.rejects(settle(prepared, {promise: Promise.resolve(receipt)}), /current task run/);
  summary.request_id = PLAN;
  summary.session_id = 'e'.repeat(32);
  await assert.rejects(settle(prepared, {promise: Promise.resolve(receipt)}), /current task run/);
})().catch((error) => {console.error(error); process.exitCode = 1;});
"""
    completed = subprocess.run(
        (str(node), "--max-old-space-size=128", "-e", harness),
        input=json.dumps(source), capture_output=True, text=True,
        timeout=20, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize("metric_id", scoped.METRIC_IDS[10:])
@pytest.mark.parametrize("field,value", [
    ("accepted", False),
    ("code", "illegal-state"),
    ("before", "pending"),
    ("after", "running"),
    ("session_id", "f" * 32),
    ("task_id", "task-" + "f" * 32),
])
def test_ui_warm_control_typed_refusal_and_identity_fail_collector_and_checker(
    metric_id: str, field: str, value: object,
) -> None:
    evidence = _evidence()
    raw = deepcopy(evidence[-1])
    wrapper = next(
        item for item in raw["children"]
        if item["receipt"]["metric_id"] == metric_id
    )
    wrapper["receipt"]["samples"][0]["correctness"][field] = value
    _rehash(wrapper)
    with pytest.raises(ValueError, match="M1-8 U control session|M1-8 U correctness"):
        _validate(*evidence[:-1], raw)

    metric = next(row for row in evidence[0]["metrics"] if row["id"] == metric_id)
    with pytest.raises(ValueError, match="M1-8 U control session|M1-8 U correctness"):
        adapter._validate_child_receipt(
            wrapper["receipt"],
            {"stage": "measurement", "metric_id": metric_id,
             "launch_token": wrapper["receipt"]["launch_token"]},
            metric, evidence[1]["headed_runtime"], set(), set(), set(), set(),
        )


@pytest.mark.parametrize("site", ("total", "warmup"))
def test_ui_script_adapter_refuses_changed_site(monkeypatch: pytest.MonkeyPatch, site: str) -> None:
    original = adapter.legacy._headed_probe_script(scoped.METRIC_IDS[1])
    if site == "total":
        changed = original.replace("initialWindow.total !== 120000", "initialWindow.total !== 119999")
    else:
        changed = original.replace("warmupCheckbox.click();", "warmupCheckbox.dispatch();")
    monkeypatch.setattr(adapter, "_original_headed_probe_script", lambda *_args, **_kwargs: changed)
    with pytest.raises(ValueError, match="adaptation site changed"):
        adapter._rootless_probe_script(scoped.METRIC_IDS[1])


@pytest.mark.parametrize("readiness", (False, True))
def test_ui_child_checks_raw_page_result_and_restores_adapters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, readiness: bool,
) -> None:
    calls = []
    evidence = _evidence()
    original_script = adapter.legacy._headed_probe_script
    original_settle = adapter.legacy._HeadedFixtureController._settle_initial_view
    metric = scoped.METRIC_IDS[1]
    reference = next(
        wrapper["receipt"] for wrapper in (
            evidence[-1]["readiness"] if readiness else evidence[-1]["children"]
        ) if (wrapper["receipt"]["metric_ids"][0] if readiness
              else wrapper["receipt"]["metric_id"]) == metric
    )

    def page(metric_contract: object, root: Path, count: int, *, readiness: bool) -> tuple[object, object, object]:
        calls.append((metric_contract["id"], root, count, readiness))
        assert adapter.legacy._headed_probe_script is adapter._rootless_probe_script
        assert adapter.legacy._HeadedFixtureController._settle_initial_view is adapter.receipt_adapter._rootless_settlement
        observed = reference["correctness"][metric] if readiness else reference["samples"]
        return deepcopy(observed), deepcopy(reference["headed_runtime"]), deepcopy(reference["headed_fixture"])

    monkeypatch.setattr(adapter.legacy, "_run_headed_page", page)
    monkeypatch.setattr(adapter.legacy, "_require_installed_runtime", lambda _root: None)
    monkeypatch.setattr(adapter.legacy, "_current_process_identity", lambda: {
        "pid": 1234, "creation_filetime_100ns": 4321,
    })
    runner = adapter.run_headed_readiness if readiness else adapter.run_headed_child
    result = runner(metric, "a" * 32, contract_path=CONTRACT_PATH,
                    benchmark_root=tmp_path, installed_root=tmp_path)
    assert result["launch_token"] == "a" * 32
    assert result["schema"] == (plan_scale.READINESS_CHILD_SCHEMA if readiness
                                else plan_scale.CHILD_RECEIPT_SCHEMA)
    assert calls == [(metric, tmp_path.resolve(), 1, readiness)]
    assert adapter.legacy._headed_probe_script is original_script
    assert adapter.legacy._HeadedFixtureController._settle_initial_view is original_settle


@pytest.mark.parametrize("readiness", (False, True))
def test_ui_child_rejects_legacy_false_control_acceptance_from_raw_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, readiness: bool,
) -> None:
    evidence = _evidence()
    metric = scoped.METRIC_IDS[10]
    reference = next(
        wrapper["receipt"] for wrapper in (
            evidence[-1]["readiness"] if readiness else evidence[-1]["children"]
        ) if (wrapper["receipt"]["metric_ids"][0] if readiness
              else wrapper["receipt"]["metric_id"]) == metric
    )

    def page(_metric: object, _root: Path, _count: int, *, readiness: bool) -> tuple[object, object, object]:
        observed = deepcopy(reference["correctness"][metric] if readiness else reference["samples"])
        if readiness:
            observed["accepted"] = False
        else:
            observed[0]["correctness"]["accepted"] = False
        return observed, deepcopy(reference["headed_runtime"]), deepcopy(reference["headed_fixture"])

    monkeypatch.setattr(adapter.legacy, "_run_headed_page", page)
    monkeypatch.setattr(adapter.legacy, "_require_installed_runtime", lambda _root: None)
    monkeypatch.setattr(adapter.legacy, "_current_process_identity", lambda: {
        "pid": 1234, "creation_filetime_100ns": 4321,
    })
    runner = adapter.run_headed_readiness if readiness else adapter.run_headed_child
    with pytest.raises(ValueError, match="M1-8 U correctness"):
        runner(metric, "a" * 32, contract_path=CONTRACT_PATH,
               benchmark_root=tmp_path, installed_root=tmp_path)


def test_ui_cold_maximum_has_unchanged_fifty_millisecond_limit() -> None:
    evidence = _evidence()
    changed = deepcopy(evidence[-1])
    wrapper = next(row for row in changed["children"] if row["receipt"]["metric_id"] == scoped.METRIC_IDS[0])
    wrapper["receipt"]["samples"][0]["elapsed_ns"] = 50_000_001
    _rehash(wrapper)
    with pytest.raises(ValueError, match="maximum exceeds"):
        _validate(*evidence[:-1], changed)


@pytest.mark.parametrize("failure_attempt", (None, 14))
def test_ui_collector_publishes_all_attempts_before_launch_and_keeps_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_attempt: int | None,
) -> None:
    evidence = _evidence()
    authority = deepcopy(evidence[3])
    compact_bytes = plan_scale.canonical_json_bytes(authority["compact_authority"])
    authority["compact_authority_receipt"] = scoped._authority_receipt(compact_bytes, plan_scale.git_blob_oid(compact_bytes))
    authority_bytes = plan_scale.canonical_json_bytes(authority)
    authority_path = tmp_path / "authority.json"
    authority_path.write_bytes(authority_bytes)
    collection_root = tmp_path / "collection"
    collection_root.mkdir()
    output = tmp_path / "receipts.json"
    originals = [*evidence[-1]["readiness"], *evidence[-1]["children"]]
    calls = []

    def child(command: list[str], **_kwargs: object) -> object:
        ordinal = len(calls) + 1
        index = json.loads((collection_root / "collection.json").read_bytes())
        assert len(index["planned"]) == 78
        assert len(index["accepted"]) == ordinal - 1
        assert index["state"]["attempt"] == ordinal
        assert index["state"]["status"] == "launching"
        token = command[command.index("--launch-token") + 1]
        assert index["planned"][ordinal - 1]["launch_token"] == token
        calls.append(command)
        if ordinal == failure_attempt:
            return subprocess.CompletedProcess(command, 17, stdout="retained", stderr="failure")
        receipt = deepcopy(originals[ordinal - 1]["receipt"])
        receipt["launch_token"] = token
        Path(command[command.index("--output") + 1]).write_bytes(plan_scale.canonical_json_bytes(receipt))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(adapter.subprocess, "run", child)
    arguments = dict(python=Path(sys.executable), authority_path=authority_path, output=output,
                     collection_root=collection_root, contract_path=CONTRACT_PATH,
                     benchmark_root=tmp_path, installed_root=tmp_path)
    if failure_attempt is not None:
        with pytest.raises(RuntimeError, match="first failure"):
            adapter.collect(**arguments)
        index = json.loads((collection_root / "collection.json").read_bytes())
        assert len(calls) == failure_attempt
        assert len(index["accepted"]) == failure_attempt - 1
        assert index["state"]["status"] == "failed"
        assert not output.exists()
        assert len(json.loads((collection_root / "failed-receipts.json").read_bytes())["receipts"]) == failure_attempt - 1
    else:
        adapter.collect(**arguments)
        raw = json.loads(output.read_bytes())
        assert len(calls) == 78
        assert len(raw["readiness"]) == 13
        assert len(raw["children"]) == 65
        assert len(_validate(evidence[0], evidence[1], compact_bytes, authority, authority_bytes, raw)) == 13
    with pytest.raises(FileExistsError, match="collection already exists"):
        adapter.collect(**arguments)
