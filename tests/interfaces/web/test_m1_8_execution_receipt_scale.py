"""Focused corruption controls for the M1-8 execution receipt evidence lane."""

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

import _m1_8_execution_receipt_scale as scoped
import _plan_review_scale as plan_scale


HERE = Path(__file__).parent
REPOSITORY_ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parents[1]))
adapter = importlib.import_module("m1_8_execution_receipt_benchmark")
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
    count = 7 if metric_id == "ui_start_execution_receipt" else 1
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
    return {
        "child_id": f"{identity:032x}",
        "correctness": {metric_id: correctness},
        "headed_fixture": _fixture(metric_id, identity * 100),
        "headed_runtime": headed_runtime,
        "launch_token": f"{identity + 10:032x}",
        "metric_ids": [metric_id],
        "process_identity": {
            "creation_filetime_100ns": identity + 10_000,
            "pid": identity + 1_000,
        },
        "schema": plan_scale.READINESS_CHILD_SCHEMA,
        "surface": "installed-headed",
    }


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
        stage = "readiness" if attempt <= 2 else "measurement"
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
    tmp_path: Path, *, raw_authority_oid: str | None = None,
) -> dict[str, object]:
    """Create a clean Git repository carrying the validator's minimal inputs."""

    source_path = "compact-source.py"
    supplemental_path = "supplemental-source.py"
    authority_path = tmp_path / "m1_8_execution_receipt_authority.json"
    receipts_path = tmp_path / "m1_8_execution_receipt_receipts.json"
    result_path = tmp_path / "m1_8_execution_receipt_result.json"
    contents = {
        source_path: b"compact source\n",
        supplemental_path: b"supplemental source\n",
    }
    for relative, content in contents.items():
        (tmp_path / relative).write_bytes(content)

    def record(relative: str) -> dict[str, str]:
        content = contents[relative]
        return {
            "git_blob_oid": plan_scale.git_blob_oid(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    compact = {"source_files": {source_path: record(source_path)}}
    authority = {"source_files": {supplemental_path: record(supplemental_path)}}
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
    for command in (
        ("git", "init", "--quiet"),
        ("git", "config", "user.email", "m1-8@example.invalid"),
        ("git", "config", "user.name", "M1-8 controls"),
        ("git", "add", "--all"),
        ("git", "commit", "--quiet", "-m", "receipt provenance fixture"),
    ):
        subprocess.run(command, cwd=tmp_path, check=True, capture_output=True, text=True)
    return {
        "authority": authority,
        "authority_path": authority_path,
        "compact": compact,
        "receipts_path": receipts_path,
        "result_path": result_path,
        "supplemental_path": supplemental_path,
    }


def test_scoped_execution_receipt_evidence_accepts_exact_two_metric_population() -> None:
    evidence = _evidence()
    observations = _validate(*evidence)

    assert [observation.metric_id for observation in observations] == list(scoped.METRIC_IDS)
    assert all(observation.budget == 100_000_000 for observation in observations)
    result = scoped.derive_result(
        json.dumps(evidence[-1], sort_keys=True, separators=(",", ":")).encode(), observations
    )
    scoped.validate_result(
        json.dumps(evidence[-1], sort_keys=True, separators=(",", ":")).encode(), observations, result
    )
    assert "passed" not in evidence[-1]


def test_scoped_execution_receipt_rejects_missing_or_reused_child_and_sample() -> None:
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
    sample_receipt = duplicate_sample["children"][0]["receipt"]
    sample_receipt["samples"][1] = deepcopy(sample_receipt["samples"][0])
    _rehash(duplicate_sample["children"][0])
    with pytest.raises(ValueError, match="correctness receipt"):
        _validate(*evidence[:-1], duplicate_sample)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda raw: raw["children"][0]["receipt"]["samples"][0].update(iteration=7),
            "correctness receipt",
        ),
        (
            lambda raw: raw["children"][0]["receipt"].update(headed_runtime={}),
            "contract is invalid",
        ),
        (
            lambda raw: raw["readiness"][0]["receipt"]["headed_fixture"]["rows"][0].update(execution_unused=False),
            "rootless headed fixture identity",
        ),
    ],
)
def test_scoped_execution_receipt_rejects_wrong_iteration_runtime_and_fixture(
    mutate: object, message: str,
) -> None:
    evidence = _evidence()
    changed = deepcopy(evidence[-1])
    mutate(changed)
    for wrapper in (*changed["children"], *changed["readiness"]):
        _rehash(wrapper)
    with pytest.raises(ValueError, match=message):
        _validate(*evidence[:-1], changed)


def test_scoped_execution_receipt_rejects_hash_and_provenance_corruption() -> None:
    evidence = _evidence()
    corrupt_hash = deepcopy(evidence[-1])
    corrupt_hash["children"][0]["receipt_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="wrapper digest"):
        _validate(*evidence[:-1], corrupt_hash)

    corrupt_provenance = deepcopy(evidence[-1])
    corrupt_provenance["authority_receipt"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="receipt authority"):
        _validate(*evidence[:-1], corrupt_provenance)

    wrong_oid = list(evidence)
    authority = deepcopy(wrong_oid[3])
    authority["compact_authority_receipt"]["git_blob_oid"] = "f" * 40
    authority_bytes = plan_scale.canonical_json_bytes(authority)
    raw = deepcopy(wrong_oid[-1])
    raw["authority_receipt"] = {
        "byte_length": len(authority_bytes), "git_blob_oid": plan_scale.git_blob_oid(authority_bytes),
        "sha256": hashlib.sha256(authority_bytes).hexdigest(),
    }
    with pytest.raises(ValueError, match="compact authority receipt"):
        scoped.validate_receipts(
            wrong_oid[0], wrong_oid[1], wrong_oid[2], plan_scale.git_blob_oid(wrong_oid[2]),
            authority, authority_bytes, plan_scale.git_blob_oid(authority_bytes), raw,
        )

    mutated_bytes = evidence[4] + b" "
    with pytest.raises(ValueError, match="authority Git identity"):
        scoped.validate_receipts(
            evidence[0], evidence[1], evidence[2], plan_scale.git_blob_oid(evidence[2]),
            evidence[3], mutated_bytes, plan_scale.git_blob_oid(evidence[4]), evidence[-1],
        )


@pytest.mark.parametrize(
    "corruption",
    ("synthetic-root", "wrong-prior-id", "wrong-public-total", "wrong-first-row-kind"),
)
def test_scoped_execution_receipt_rejects_rootless_settlement_corruption(corruption: str) -> None:
    evidence = _evidence()
    raw = deepcopy(evidence[-1])
    settlement = raw["readiness"][0]["receipt"]["headed_fixture"]["rows"][0]["initial_view_settlement"]
    first_row = settlement["first_row"]
    if corruption == "synthetic-root":
        first_row["node_id"] = plan_scale._independent_plan_root_node_id(settlement["request_id"])
    elif corruption == "wrong-prior-id":
        first_row["node_id"] = "node-" + "0" * 32
    elif corruption == "wrong-public-total":
        settlement["window_total"] = 120_000
    else:
        first_row["row_kind"] = "folder"
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


def test_scoped_execution_receipt_retains_first_failure_and_refuses_replacement() -> None:
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

    failed["failures"].append(deepcopy(failed["failures"][0]))
    with pytest.raises(ValueError, match="failure population"):
        _validate(*evidence[:-1], failed)

    reused_token = deepcopy(evidence[-1])
    reused_token["failures"] = [deepcopy(failed["failures"][0])]
    reused_token["failures"][0]["launch_token"] = reused_token["children"][0]["receipt"]["launch_token"]
    with pytest.raises(ValueError, match="launch token is reused"):
        _validate(*evidence[:-1], reused_token)


def test_scoped_execution_receipt_rejects_p95_and_maximum_only_breaches() -> None:
    evidence = _evidence()
    p95_breach = deepcopy(evidence[-1])
    for wrapper in p95_breach["children"]:
        if wrapper["receipt"]["metric_id"] == scoped.METRIC_IDS[0]:
            for sample in wrapper["receipt"]["samples"]:
                sample["elapsed_ns"] = 100_000_001
            _rehash(wrapper)
    with pytest.raises(ValueError, match="statistic exceeds"):
        _validate(*evidence[:-1], p95_breach)

    maximum_breach = deepcopy(evidence[-1])
    maximum_breach["children"][0]["receipt"]["samples"][0]["elapsed_ns"] = 250_000_001
    _rehash(maximum_breach["children"][0])
    with pytest.raises(ValueError, match="maximum exceeds"):
        _validate(*evidence[:-1], maximum_breach)


def test_scoped_execution_receipt_harmless_variation_changes_retained_observation() -> None:
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
        (lambda raw: raw["collection"]["planned"].__setitem__(1, deepcopy(raw["collection"]["planned"][0])), "collection planned attempt"),
        (lambda raw: raw["collection"].update(state={"status": "launching"}), "collection is not complete"),
        (lambda raw: raw["collection"]["accepted"][0].update(receipt_sha256="0" * 64), "collection accepted attempt"),
    ],
)
def test_scoped_execution_receipt_rejects_durable_index_corruption(
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


@pytest.mark.parametrize("timed_out", (False, True))
def test_scoped_adapter_persists_first_failure_before_any_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, timed_out: bool,
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
        if timed_out:
            raise subprocess.TimeoutExpired(command, 300, output=b"stdout", stderr=b"stderr")
        return subprocess.CompletedProcess(command, 17, stdout="stdout", stderr="stderr")

    monkeypatch.setattr(adapter.subprocess, "run", fail)
    with pytest.raises(RuntimeError, match="first failure"):
        adapter.collect(
            python=Path(sys.executable), authority_path=authority_path,
            output=tmp_path / "receipts.json", collection_root=collection_root,
            contract_path=CONTRACT_PATH, benchmark_root=tmp_path, installed_root=tmp_path,
        )
    index = json.loads((collection_root / "collection.json").read_bytes())
    failed = index["state"]
    assert len(calls) == 1
    assert failed["status"] == "failed"
    assert failed["attempt"] == 1
    assert failed["failure"]["timed_out"] is timed_out
    assert failed["failure"]["exit_code"] is (None if timed_out else 17)
    assert (collection_root / "failed-receipts.json").is_file()
    assert (collection_root / "logs" / "01.log").read_bytes() == b"stdoutstderr"
