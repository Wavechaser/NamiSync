"""Contract tests for the SH-G-8 transport-custody evidence runner."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from types import SimpleNamespace
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
PARENT = ROOT / "bridge_transport_custody.py"
CHILD = Path(__file__).with_name("_bridge_transport_custody.py")
RETAINED = Path(__file__).with_name("_bridge_retained_memory.py")
CALIBRATION = Path(__file__).with_name("sh_g_8_transport_calibration.json")
TESTED_COMMIT = "0" * 40
VARIANT = "calibration-a"

_CALIBRATION_COMMIT = "56c50b43dc19090ad33af031891503bfec80599b"
_CALIBRATION_SHA256 = (
    "13589307538eb90f05da2322c7e0ba627234e060c8455d9b7e3013aa575cece8"
)


def _module(path: Path, name: str):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _child_module():
    return _module(CHILD, "bridge_transport_custody_child_test")


def _parent_module():
    return _module(PARENT, "bridge_transport_custody_parent_test")


def _artifact_source_authority(artifact: dict[str, object]) -> dict[str, object]:
    hashes = artifact["hashes"]
    return {
        "tested_commit": artifact["tested_commit"],
        "source_files": copy.deepcopy(hashes["source_files"]),
        "source_sha256": hashes["source_sha256"],
        "instrument_sha256": hashes["instrument_sha256"],
    }


def _artifact_dependency_authority(
    artifact: dict[str, object],
) -> dict[str, object]:
    return copy.deepcopy(artifact["dependency_authority"])


def _artifact_pycache_prefix(artifact: dict[str, object]) -> Path:
    return Path(artifact["runtime"]["pycache_prefix"])


@pytest.fixture(scope="module")
def custody_execution(tmp_path_factory: pytest.TempPathFactory):
    parent = _parent_module()
    root = tmp_path_factory.mktemp("bridge-custody-parent")
    output = root / "run.json"
    completed = parent._run_child(
        root / "fixture",
        output,
        variant=VARIANT,
        tested_commit=TESTED_COMMIT,
        dependency_root=parent._dependency_root(),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    artifact = json.loads(output.read_text(encoding="utf-8"))
    receipt = parent._read_child_receipt(
        completed.stdout,
        variant=VARIANT,
        tested_commit=TESTED_COMMIT,
    )
    parent._validate_child_receipt(receipt, artifact)
    return artifact, receipt


@pytest.fixture(scope="module")
def custody_run(custody_execution):
    return custody_execution[0]


def test_transport_custody_sources_compile_and_freeze_measurement_policy() -> None:
    child_source = CHILD.read_text(encoding="utf-8")
    parent_source = PARENT.read_text(encoding="utf-8")
    compile(child_source, str(CHILD), "exec")
    compile(parent_source, str(PARENT), "exec")
    child = _child_module()

    assert child.CORPUS_VERSION == "sh-g-8-transport-v1"
    assert child.HEADROOM_POLICY == {
        "factor_numerator": 5,
        "factor_denominator": 4,
        "round_up_bytes": 65_536,
        "rule": (
            "round upward to 65536 bytes after applying 25 percent headroom "
            "to the largest calibration transport_custody_bytes measurement"
        ),
    }
    assert "measure_retained_bridge_state" in child_source
    assert "NamiSyncService" in child_source
    assert "TaskRegistry" in child_source
    assert "subprocess.run" in parent_source
    assert "range(3)" in parent_source
    assert "_ObservedDeque" not in child_source
    assert "sys.path.insert(0, str(_ROOT.resolve()))" in child_source
    assert "ceiling_bytes" not in child_source
    assert "ceiling_bytes" not in parent_source


def test_parent_contract_executes_exact_verified_source_bytes(custody_run) -> None:
    parent = _parent_module()
    authority = _artifact_source_authority(custody_run)
    contract = parent._load_child_contract(authority)
    assert contract.__file__ == str(parent.CHILD)
    assert not hasattr(contract, "__cached__")
    assert tuple(authority["source_files"]) == tuple(
        path.as_posix() for path in contract._SOURCE_FILES
    )

    corrupt = copy.deepcopy(authority)
    relative = parent.CHILD.relative_to(parent.REPOSITORY_ROOT).as_posix()
    corrupt["source_files"][relative] = "0" * 64
    with pytest.raises(RuntimeError, match="changed before load"):
        parent._load_child_contract(corrupt)


@pytest.mark.parametrize("variant", ["calibration-a", "holdout-b"])
def test_frozen_corpus_has_exact_lengths_depth_alphabets_and_unique_values(
    variant: str,
) -> None:
    child = _child_module()
    profiles = (
        (600, (570, 24, 6), "ordinary-item"),
        (516, (490, 21, 5), "maximum-item"),
        (6_000, (5_700, 240, 60), "ordinary-progress"),
    )
    for population, counts, kind in profiles:
        paths = [
            child._payload_path(
                kind,
                ordinal,
                child._length_for(ordinal, population, counts, variant),
                variant,
            )
            for ordinal in range(population)
        ]
        assert len(set(paths)) == population
        assert len({id(path) for path in paths}) == population
        assert Counter(map(child._utf16_units, paths)) == {
            240: counts[0],
            1_024: counts[1],
            4_096: counts[2],
        }
        assert Counter(
            "ascii"
            if path.isascii()
            else "non_bmp"
            if any(ord(character) > 0xFFFF for character in path)
            else "bmp"
            for path in paths
        ) == {
            "ascii": population // 2,
            "bmp": population // 4,
            "non_bmp": population // 4,
        }
        assert all(path.count("\\") == 31 for path in paths)

    contracts = (
        (
            "copy",
            "failed",
            "io-error",
            {
                "error_type",
                "message",
                "cleanup_error",
                "publish_state",
                "published_path",
                "durable_state",
                "state_error_type",
                "state_error",
                "recording",
                "recording_error",
            },
        ),
        (
            "move_update",
            "failed",
            "recorder-failed",
            {
                "error_type",
                "message",
                "target_state",
                "publish_state",
                "published_path",
                "prior_path",
                "trash_path",
                "durable_state",
                "recording",
                "recording_error",
            },
        ),
        (
            "update",
            "failed",
            "io-error",
            {
                "error_type",
                "message",
                "publish_state",
                "mutation_state",
                "durable_state",
                "mutation_state_error",
                "recording",
                "recording_error",
            },
        ),
    )
    dynamic = []
    subjects = []
    marker = f"x{variant.replace('-', 'x')}x"
    for length_index, length in enumerate((240, 1_024, 4_096)):
        for family, (kind, outcome, reason, keys) in enumerate(contracts):
            ordinal = family + length_index * 3
            actual_kind, actual_outcome, actual_reason = child._item_contract(
                ordinal
            )
            subject = child._payload_path(
                "ordinary-item", ordinal, length, variant
            )
            detail = child._detail(
                ordinal, length, "ordinary", variant, subject
            )
            subjects.append(subject)
            assert (
                actual_kind,
                actual_outcome.value,
                actual_reason,
            ) == (kind, outcome, reason)
            assert set(detail) == keys
            assert detail["recording"] == "degraded"
            if family == 0:
                assert detail["published_path"] is subject
                assert detail["error_type"] == "PermissionError"
                assert detail["publish_state"] == "unverified"
                assert detail["durable_state"] == "publication-unverified"
                assert detail["state_error_type"] == "PermissionError"
                assert detail["recording_error"] == (
                    "filesystem mutation may have published but durable state "
                    "could not be verified"
                )
            elif family == 1:
                assert detail["published_path"] is subject
                assert detail["error_type"] == "OperationFailure"
                assert detail["target_state"] == "published"
                assert detail["publish_state"] == "published"
                assert detail["durable_state"] == "new-and-old"
                assert detail["recording_error"] == (
                    "published filesystem mutation failed before ledger "
                    "settlement"
                )
                prefix, run_id, prior_path = detail["trash_path"].split(
                    "\\", 2
                )
                assert prefix == ".synctrash"
                assert re.fullmatch(r"[0-9a-f]{32}", run_id)
                assert prior_path is not detail["prior_path"]
                assert prior_path == detail["prior_path"]
            else:
                assert "published_path" not in detail
                assert detail["error_type"] == "PermissionError"
                assert detail["publish_state"] == "not-published"
                assert detail["mutation_state"] == "unverified"
                assert detail["durable_state"] == "update-state-unverified"
                assert detail["recording_error"] == (
                    "filesystem mutation may have committed before ledger "
                    "settlement"
                )
            warnings = detail.get("durability_warnings", ())
            assert len(warnings) == 0
            assert all(
                warning.startswith("parent directory flush unsupported: ")
                for warning in warnings
            )
            values = [
                value
                for value in (*detail.values(), *warnings)
                if isinstance(value, str) and "\\" in value
            ]
            for value in values:
                embedded = value[value.index(marker) :]
                child._validate_path(embedded, length)
            dynamic.extend(values)
            assert "mutation_destination" not in detail
            assert "source_state" not in detail
            assert "destination_state" not in detail
            assert "backup_path" not in detail
            assert "backup_state" not in detail
    assert len(subjects) == len(set(subjects)) == len({id(value) for value in subjects})
    assert len(dynamic) == len(set(dynamic)) == len({id(value) for value in dynamic})
    assert child.CORPUS_SPEC["detail_families"] == {
        "publication": {
            "kind": "copy",
            "outcome": "failed",
            "reason": "io-error",
            "durability_warnings": 0,
        },
        "move_update": {
            "kind": "move_update",
            "outcome": "failed",
            "reason": "recorder-failed",
            "durability_warnings": 0,
        },
        "mutation": {
            "kind": "update",
            "outcome": "failed",
            "reason": "io-error",
            "durability_warnings": 0,
        },
    }
    assert child.CORPUS_SPEC["identity_aliases"] == {
        "copy_published_path": "ItemOutcome.path",
        "move_update_published_path": "ItemOutcome.path",
    }


def test_calibration_and_holdout_dynamic_corpora_are_disjoint() -> None:
    child = _child_module()
    calibration = {
        child._payload_path(
            "ordinary-item",
            ordinal,
            child._length_for(ordinal, 600, (570, 24, 6), "calibration-a"),
            "calibration-a",
        )
        for ordinal in range(600)
    }
    holdout = {
        child._payload_path(
            "ordinary-item",
            ordinal,
            child._length_for(ordinal, 600, (570, 24, 6), "holdout-b"),
            "holdout-b",
        )
        for ordinal in range(600)
    }
    assert calibration.isdisjoint(holdout)
    calibration_order = [
        child._length_for(item, 600, (570, 24, 6), "calibration-a")
        for item in range(600)
    ]
    holdout_order = [
        child._length_for(item, 600, (570, 24, 6), "holdout-b")
        for item in range(600)
    ]
    assert calibration_order != holdout_order
    assert child._canonical_hash(
        child._structural_facts("calibration-a")
    ) != child._canonical_hash(child._structural_facts("holdout-b"))
    item_ids = {
        variant: {
            child._item_id(variant, fixture, task, local)
            for fixture, count in (("ordinary", 150), ("maximum", 129))
            for task in range(4)
            for local in range(count)
        }
        for variant in ("calibration-a", "holdout-b")
    }
    assert item_ids["calibration-a"].isdisjoint(item_ids["holdout-b"])
    assert all(
        re.fullmatch(r"[0-9a-f]{32}", item_id)
        for values in item_ids.values()
        for item_id in values
    )
    assert all(len(values) == (150 + 129) * 4 for values in item_ids.values())


def test_module_origin_check_rejects_shadowed_project_code(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    child = _child_module()
    shadow = tmp_path / "event_bus.py"
    shadow.write_text("# shadow\n", encoding="utf-8")
    monkeypatch.setitem(
        sys.modules,
        "namisync.dispatcher.event_bus",
        SimpleNamespace(__file__=str(shadow)),
    )
    with pytest.raises(RuntimeError, match="outside tested source"):
        child._module_origins(
            child._dependency_authority(
                Path(sys.executable).resolve().parent.parent
                / "Lib"
                / "site-packages"
            )
        )


def test_transport_custody_fixture_uses_real_paths_and_exact_maximum_shape(
    custody_run,
) -> None:
    parent = _parent_module()
    child = _child_module()
    parent._validate_run_artifact(
        custody_run,
        child,
        variant=VARIANT,
        source_authority=_artifact_source_authority(custody_run),
        dependency_authority=_artifact_dependency_authority(custody_run),
        expected_pycache_prefix=_artifact_pycache_prefix(custody_run),
    )

    ordinary_queues = custody_run["ordinary"]["observed_checkpoint_peak"]
    assert ordinary_queues == {
        "replay": {"per_queue": [128, 128, 128, 128], "maximum": 128},
        "subscriber": {"per_queue": [0, 0, 0, 0], "maximum": 0},
        "adapter": {"per_queue": [4, 4, 4, 4], "maximum": 4},
    }
    assert custody_run["maximum_no_gap"]["queue_lengths"] == {
        "replay": [128, 128, 128, 128],
        "subscriber": [64, 64, 64, 64],
        "adapter": [64, 64, 64, 64],
    }
    assert custody_run["maximum_no_gap"]["no_gap"] is True
    assert custody_run["ordinary"]["root_container_type"] == "collections.deque"
    assert custody_run["maximum_no_gap"]["root_container_type"] == "collections.deque"
    assert custody_run["maximum_no_gap"]["cleanup_delivery"] == {
        "outcomes": 516,
        "outcomes_per_task": [129, 129, 129, 129],
        "terminal_events": 4,
        "terminal_records": 4,
        "terminal_order_exact": True,
        "failed_state_headline_records": 4,
    }
    assert custody_run["ordinary"]["ordinary_quiescent_peak"][
        "transport_custody_bytes"
    ] > 0
    assert custody_run["maximum_no_gap"]["custody"][
        "transport_custody_bytes"
    ] > 0
    for measurement, strict_shared in (
        (custody_run["ordinary"]["ordinary_quiescent_peak"], False),
        (custody_run["maximum_no_gap"]["custody"], True),
    ):
        components = [
            measurement[f"{role}_queue_bytes"]
            for role in ("replay", "subscriber", "adapter")
        ]
        union = measurement["transport_custody_bytes"]
        assert max(components) <= union <= sum(components)
        if strict_shared:
            assert union < sum(components)
        assert measurement["terminal_artifact_bytes"] == 0
        assert measurement["terminal_artifact_objects"] == 0
    witness = custody_run["ordinary"]["terminal_path_cut_witness"]
    assert witness["authority"] == "BR-G-45-nonnormative"
    assert witness["transport_result_exclusion_exercised"] is True
    assert witness["measurement"]["terminal_artifact_bytes"] > 0
    assert witness["measurement"]["terminal_artifact_objects"] > 0
    assert witness["measurement"]["transport_custody_bytes"] < witness[
        "measurement"
    ]["terminal_artifact_bytes"]
    assert custody_run["hashes"]["evidence_sha256"] == parent._canonical_hash(
        {
            "ordinary": custody_run["ordinary"],
            "maximum_no_gap": custody_run["maximum_no_gap"],
        }
    )
    runtime = custody_run["runtime"]
    assert runtime["implementation"] == "CPython"
    assert runtime["version_info"][:2] == [3, 13]
    assert runtime["version_info"][3:] == ["final", 0]
    assert runtime["pointer_bits"] == 64
    assert runtime["py_debug"] == 0
    assert runtime["with_pymalloc_config"] is None
    assert (
        runtime["allocator_predicate"]
        == "explicit-pymalloc-on-qualified-Windows-CPython"
    )
    assert runtime["python_hash_seed"] == "0"
    assert runtime["python_malloc"] == "pymalloc"
    assert runtime["no_site"] == 1
    assert runtime["safe_path"] is True
    assert runtime["pycache_prefix"] == str(
        _artifact_pycache_prefix(custody_run)
    )
    assert runtime["pycache_prefix_role"] == (
        "fresh-empty-per-child-outside-source-tree"
    )
    assert runtime["dependency_root"] == custody_run["dependency_authority"][
        "root"
    ]
    assert runtime["optimize"] == 0
    assert runtime["dev_mode"] is False
    assert runtime["tracemalloc"] is False
    assert runtime["qualifier_environment"] == {
        "PYTHONHASHSEED": "0",
        "PYTHONMALLOC": "pymalloc",
        "PYTHONNOUSERSITE": "1",
        "PYTHONUTF8": "1",
        "PYTHONPYCACHEPREFIX": runtime["pycache_prefix"],
    }
    dependency = custody_run["dependency_authority"]
    assert set(dependency) == {"root", "files", "sha256"}
    assert set(dependency["files"]) >= {
        "xxhash/__init__.py",
        "xxhash/version.py",
    }
    assert len(dependency["files"]) == 3
    assert dependency["sha256"] == parent._canonical_hash(dependency["files"])
    assert custody_run["hashes"]["runtime_qualifier_sha256"] == (
        parent._canonical_hash(parent._runtime_qualifier(runtime))
    )


def test_xxhash_dependency_authority_is_exact_and_separate(
    custody_run,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _parent_module()
    child = _child_module()
    authority = _artifact_dependency_authority(custody_run)
    root = Path(authority["root"])
    assert parent._dependency_authority(root) == authority
    assert child._dependency_authority(root) == authority
    assert authority["sha256"] == parent._canonical_hash(authority["files"])
    assert set(authority["files"]) == {
        "xxhash/__init__.py",
        "xxhash/version.py",
        next(
            path
            for path in authority["files"]
            if path.startswith("xxhash/_xxhash") and path.endswith(".pyd")
        ),
    }
    assert all(
        digest == hashlib.sha256((root / path).read_bytes()).hexdigest()
        for path, digest in authority["files"].items()
    )

    changed = copy.deepcopy(authority)
    changed["sha256"] = "f" * 64
    monkeypatch.setattr(
        parent, "_dependency_authority", lambda _root=None: changed
    )
    with pytest.raises(RuntimeError, match="changed during runs"):
        parent._verify_dependency_authority(authority)


def test_runtime_qualifier_normalizes_only_fresh_pycache_identity(
    custody_run,
) -> None:
    parent = _parent_module()
    first = copy.deepcopy(custody_run["runtime"])
    second = copy.deepcopy(first)
    second["pycache_prefix"] = str(
        Path(first["pycache_prefix"]).with_name("another-fresh-pycache")
    )
    second["qualifier_environment"]["PYTHONPYCACHEPREFIX"] = second[
        "pycache_prefix"
    ]
    assert parent._canonical_hash(first) != parent._canonical_hash(second)
    assert parent._canonical_hash(parent._runtime_qualifier(first)) == (
        parent._canonical_hash(parent._runtime_qualifier(second))
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("with_pymalloc_config", 0),
        ("python_malloc", "default"),
        ("no_site", 0),
        ("safe_path", False),
        ("platform", "Linux-qualifier-lookalike"),
    ],
)
def test_windows_pymalloc_qualifier_rejects_ambiguous_profiles(
    custody_run,
    field: str,
    value: object,
) -> None:
    parent = _parent_module()
    child = _child_module()
    artifact = copy.deepcopy(custody_run)
    artifact["runtime"][field] = value
    artifact["hashes"]["runtime_sha256"] = parent._canonical_hash(
        artifact["runtime"]
    )
    artifact["hashes"]["runtime_qualifier_sha256"] = parent._canonical_hash(
        parent._runtime_qualifier(artifact["runtime"])
    )
    with pytest.raises(ValueError, match="frozen qualifier"):
        parent._validate_run_artifact(
            artifact,
            child,
            variant=VARIANT,
            source_authority=_artifact_source_authority(custody_run),
            dependency_authority=_artifact_dependency_authority(custody_run),
            expected_pycache_prefix=_artifact_pycache_prefix(custody_run),
        )


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda artifact: artifact.update(schema_version=2),
        lambda artifact: artifact["hashes"].update(runtime_sha256="0" * 64),
        lambda artifact: artifact["hashes"].update(
            runtime_qualifier_sha256="0" * 64
        ),
        lambda artifact: artifact["dependency_authority"].update(
            sha256="0" * 64
        ),
        lambda artifact: artifact["structural_facts"].update(task_count=3),
        lambda artifact: artifact["ordinary"]["delivered"].update(outcomes=599),
        lambda artifact: artifact["maximum_no_gap"]["queue_lengths"].update(
            replay=[127, 128, 128, 128]
        ),
        lambda artifact: artifact["maximum_no_gap"]["cleanup_delivery"].update(
            outcomes=515
        ),
        lambda artifact: artifact["maximum_no_gap"]["custody"].update(
            unknown_bytes=1
        ),
        lambda artifact: artifact["ordinary"]["ordinary_quiescent_peak"].update(
            transport_custody_bytes=1
        ),
        lambda artifact: artifact.update(acceptance=True),
    ],
)
def test_transport_custody_artifact_schema_rejects_corruption(
    custody_run,
    corrupt,
) -> None:
    parent = _parent_module()
    child = _child_module()
    artifact = copy.deepcopy(custody_run)
    corrupt(artifact)
    with pytest.raises(ValueError):
        parent._validate_run_artifact(
            artifact,
            child,
            variant=VARIANT,
            source_authority=_artifact_source_authority(custody_run),
            dependency_authority=_artifact_dependency_authority(custody_run),
            expected_pycache_prefix=_artifact_pycache_prefix(custody_run),
        )


def test_transport_custody_artifact_rejects_rehashed_implausible_measurement(
    custody_run,
) -> None:
    parent = _parent_module()
    child = _child_module()
    artifact = copy.deepcopy(custody_run)
    artifact["ordinary"]["ordinary_quiescent_peak"][
        "transport_custody_bytes"
    ] = 1
    artifact["hashes"]["evidence_sha256"] = parent._canonical_hash(
        {
            "ordinary": artifact["ordinary"],
            "maximum_no_gap": artifact["maximum_no_gap"],
        }
    )
    with pytest.raises(ValueError, match="density|accounting"):
        parent._validate_run_artifact(
            artifact,
            child,
            variant=VARIANT,
            source_authority=_artifact_source_authority(custody_run),
            dependency_authority=_artifact_dependency_authority(custody_run),
            expected_pycache_prefix=_artifact_pycache_prefix(custody_run),
        )


def test_child_receipt_rejects_plausible_rehashed_artifact_edit(
    custody_execution,
) -> None:
    parent = _parent_module()
    child = _child_module()
    original, receipt = custody_execution
    artifact = copy.deepcopy(original)
    artifact["maximum_no_gap"]["custody"]["transport_custody_bytes"] += 64
    artifact["hashes"]["evidence_sha256"] = parent._canonical_hash(
        {
            "ordinary": artifact["ordinary"],
            "maximum_no_gap": artifact["maximum_no_gap"],
        }
    )
    parent._validate_run_artifact(
        artifact,
        child,
        variant=VARIANT,
        source_authority=_artifact_source_authority(original),
        dependency_authority=_artifact_dependency_authority(original),
        expected_pycache_prefix=_artifact_pycache_prefix(original),
    )
    with pytest.raises(ValueError, match="receipt does not match"):
        parent._validate_child_receipt(receipt, artifact)


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda receipt: receipt.update(extra=True),
        lambda receipt: receipt.update(dataset_variant="holdout-b"),
        lambda receipt: receipt.update(artifact_sha256="z" * 64),
    ],
)
def test_child_receipt_schema_rejects_corruption(
    custody_execution,
    corrupt,
) -> None:
    parent = _parent_module()
    receipt = copy.deepcopy(custody_execution[1])
    corrupt(receipt)
    with pytest.raises(ValueError, match="receipt fields"):
        parent._read_child_receipt(
            json.dumps(receipt),
            variant=VARIANT,
            tested_commit=TESTED_COMMIT,
        )


def test_transport_custody_artifact_reader_rejects_invalid_json(
    tmp_path: Path,
) -> None:
    parent = _parent_module()
    child = _child_module()
    artifact = tmp_path / "corrupt.json"
    artifact.write_text('{"schema_version":', encoding="utf-8")
    with pytest.raises(ValueError, match="unreadable"):
        parent._read_run_artifact(
            artifact,
            child,
            variant=VARIANT,
            source_authority={
                "tested_commit": TESTED_COMMIT,
                "source_files": {},
                "source_sha256": "",
                "instrument_sha256": "",
            },
            dependency_authority={"root": "", "files": {}, "sha256": ""},
            expected_pycache_prefix=tmp_path / "pycache",
        )


def test_dataset_uses_three_distinct_runs_without_acceptance_or_limit(
    custody_run,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    parent = _parent_module()
    next_process_id = iter((101, 102, 103))

    def run_child(
        run_root: Path,
        output: Path,
        *,
        variant: str,
        tested_commit: str,
        dependency_root: Path,
    ):
        assert variant == VARIANT
        assert tested_commit == TESTED_COMMIT
        assert dependency_root == Path(custody_run["dependency_authority"]["root"])
        artifact = copy.deepcopy(custody_run)
        artifact["process_id"] = next(next_process_id)
        prefix = parent._child_pycache_prefix(run_root)
        artifact["runtime"]["pycache_prefix"] = str(prefix)
        artifact["runtime"]["qualifier_environment"][
            "PYTHONPYCACHEPREFIX"
        ] = str(prefix)
        artifact["hashes"]["runtime_sha256"] = parent._canonical_hash(
            artifact["runtime"]
        )
        artifact["hashes"]["runtime_qualifier_sha256"] = (
            parent._canonical_hash(
                parent._runtime_qualifier(artifact["runtime"])
            )
        )
        output.write_text(json.dumps(artifact), encoding="utf-8")
        receipt = {
            "schema_version": 1,
            "gate": artifact["gate"],
            "dataset_variant": artifact["dataset_variant"],
            "tested_commit": artifact["tested_commit"],
            "process_id": artifact["process_id"],
            "evidence_sha256": artifact["hashes"]["evidence_sha256"],
            "artifact_sha256": parent._canonical_hash(artifact),
        }
        return subprocess.CompletedProcess([], 0, json.dumps(receipt), "")

    monkeypatch.setattr(parent, "_run_child", run_child)
    monkeypatch.setattr(parent, "_require_authoritative_parent", lambda: None)
    source_authority = _artifact_source_authority(custody_run)
    monkeypatch.setattr(
        parent, "_source_authority", lambda: source_authority
    )
    monkeypatch.setattr(
        parent,
        "_dependency_authority",
        lambda _root=None: _artifact_dependency_authority(custody_run),
    )
    dataset = parent.build_dataset("calibration", tmp_path)

    assert dataset["run_count"] == 3
    assert dataset["dataset_variant"] == VARIANT
    assert dataset["tested_commit"] == TESTED_COMMIT
    assert [run["process_id"] for run in dataset["runs"]] == [101, 102, 103]
    assert [
        receipt["process_id"] for receipt in dataset["run_receipts"]
    ] == [101, 102, 103]
    assert dataset["headroom_policy"]["round_up_bytes"] == 65_536

    def keys(value: object):
        if isinstance(value, dict):
            for key, child_value in value.items():
                yield str(key)
                yield from keys(child_value)
        elif isinstance(value, list):
            for child_value in value:
                yield from keys(child_value)

    evidence_keys = set(keys(dataset))
    assert "acceptance" not in evidence_keys
    assert "passed" not in evidence_keys
    assert "ceiling_bytes" not in evidence_keys
    assert "limit_bytes" not in evidence_keys


def test_committed_calibration_is_raw_three_process_evidence() -> None:
    parent = _parent_module()
    child = _child_module()
    artifact = json.loads(CALIBRATION.read_text(encoding="utf-8"))

    assert hashlib.sha256(CALIBRATION.read_bytes()).hexdigest() == (
        _CALIBRATION_SHA256
    )
    assert set(artifact) == {
        "schema_version",
        "gate",
        "dataset_kind",
        "dataset_variant",
        "tested_commit",
        "dependency_authority",
        "corpus_version",
        "run_count",
        "headroom_policy",
        "hashes",
        "structural_facts",
        "measurement_maxima",
        "run_receipts",
        "runs",
    }
    assert artifact["schema_version"] == 1
    assert artifact["gate"] == "SH-G-8 transport custody"
    assert artifact["dataset_kind"] == "calibration"
    assert artifact["dataset_variant"] == "calibration-a"
    assert artifact["tested_commit"] == _CALIBRATION_COMMIT
    assert artifact["run_count"] == 3
    assert artifact["corpus_version"] == child.CORPUS_VERSION
    assert artifact["headroom_policy"] == child.HEADROOM_POLICY
    assert artifact["structural_facts"] == child._structural_facts(
        "calibration-a"
    )

    runs = artifact["runs"]
    receipts = artifact["run_receipts"]
    assert len(runs) == len(receipts) == 3
    assert len({run["process_id"] for run in runs}) == 3
    assert artifact["hashes"] == runs[0]["hashes"]
    source_authority = _artifact_source_authority(runs[0])
    dependency_authority = artifact["dependency_authority"]
    for run, receipt in zip(runs, receipts, strict=True):
        assert _artifact_source_authority(run) == source_authority
        assert _artifact_dependency_authority(run) == dependency_authority
        parent._validate_archived_run_artifact(
            run,
            child,
            variant="calibration-a",
            source_authority=source_authority,
            dependency_authority=dependency_authority,
            expected_pycache_prefix=_artifact_pycache_prefix(run),
        )
        parsed_receipt = parent._read_child_receipt(
            json.dumps(receipt),
            variant="calibration-a",
            tested_commit=_CALIBRATION_COMMIT,
        )
        parent._validate_child_receipt(parsed_receipt, run)

    assert artifact["measurement_maxima"] == parent._measurement_maxima(
        runs
    )
    assert artifact["measurement_maxima"]["ordinary_quiescent_peak"][
        "transport_custody_bytes"
    ] == 1_376_690
    assert artifact["measurement_maxima"]["maximum_no_gap_custody"][
        "transport_custody_bytes"
    ] == 1_534_946

    def keys(value: object):
        if isinstance(value, dict):
            for key, child_value in value.items():
                yield str(key)
                yield from keys(child_value)
        elif isinstance(value, list):
            for child_value in value:
                yield from keys(child_value)

    evidence_keys = set(keys(artifact))
    assert "acceptance" not in evidence_keys
    assert "passed" not in evidence_keys
    assert "ceiling_bytes" not in evidence_keys
    assert "limit_bytes" not in evidence_keys


def test_archived_run_validation_is_checkout_path_independent(
    tmp_path: Path,
) -> None:
    parent = _parent_module()
    child = _child_module()
    artifact = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    run = copy.deepcopy(artifact["runs"][0])
    source_root = tmp_path / "relocated" / "NamiSync"
    dependency_root = source_root / ".venv" / "Lib" / "site-packages"
    pycache_prefix = tmp_path / "relocated-cache"
    dependency_authority = copy.deepcopy(run["dependency_authority"])
    dependency_authority["root"] = str(dependency_root.resolve())
    run["dependency_authority"] = dependency_authority

    module_origins = {
        name: str((source_root / relative).resolve())
        for name, relative in child._MODULE_PATHS.items()
    }
    extension = next(
        name
        for name in dependency_authority["files"]
        if name.startswith("xxhash/_xxhash")
    )
    module_origins.update(
        {
            "xxhash": str(
                (dependency_root / "xxhash/__init__.py").resolve()
            ),
            "xxhash.version": str(
                (dependency_root / "xxhash/version.py").resolve()
            ),
            "xxhash._xxhash": str((dependency_root / extension).resolve()),
        }
    )
    run["module_origins"] = module_origins
    runtime = run["runtime"]
    runtime["executable"] = str(
        (source_root / ".venv" / "Scripts" / "python.exe").resolve()
    )
    runtime["dependency_root"] = str(dependency_root.resolve())
    runtime["pycache_prefix"] = str(pycache_prefix.resolve())
    runtime["qualifier_environment"]["PYTHONPYCACHEPREFIX"] = str(
        pycache_prefix.resolve()
    )
    run["hashes"]["runtime_sha256"] = parent._canonical_hash(runtime)
    run["hashes"]["runtime_qualifier_sha256"] = parent._canonical_hash(
        parent._runtime_qualifier(runtime)
    )
    source_authority = _artifact_source_authority(run)

    with pytest.raises(ValueError, match="module origins drifted"):
        parent._validate_run_artifact(
            run,
            child,
            variant="calibration-a",
            source_authority=source_authority,
            dependency_authority=dependency_authority,
            expected_pycache_prefix=pycache_prefix,
        )
    parent._validate_archived_run_artifact(
        run,
        child,
        variant="calibration-a",
        source_authority=source_authority,
        dependency_authority=dependency_authority,
        expected_pycache_prefix=pycache_prefix,
    )


def test_authoritative_parent_requires_isolated_safe_no_site_startup() -> None:
    script = (
        "import runpy; "
        f"runpy.run_path({str(PARENT)!r})['_require_authoritative_parent']()"
    )
    authoritative = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    merely_safe = subprocess.run(
        [sys.executable, "-P", "-S", "-c", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert authoritative.returncode == 0, (
        authoritative.stdout + authoritative.stderr
    )
    assert merely_safe.returncode != 0
    assert "must be launched with Python -I -S" in merely_safe.stderr


def test_child_process_environment_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    parent = _parent_module()
    captured = {}

    def run(*_args, **kwargs):
        captured["arguments"] = _args[0]
        captured.update(kwargs)
        return subprocess.CompletedProcess([], 0, "", "")

    sanitized = {
        "PYTHONASYNCIODEBUG",
        "PYTHONDEVMODE",
        "PYTHONFAULTHANDLER",
        "PYTHONHOME",
        "PYTHONINSPECT",
        "PYTHONOPTIMIZE",
        "PYTHONPATH",
        "PYTHONPROFILEIMPORTTIME",
        "PYTHONTRACEMALLOC",
        "PYTHONUSERBASE",
        "PYTHONWARNINGS",
        "PYTHON_FUTURE_CONTAMINATION",
    }
    for name in sanitized:
        monkeypatch.setenv(name, "host-contamination")
    monkeypatch.setattr(parent.subprocess, "run", run)
    parent._run_child(
        tmp_path / "root",
        tmp_path / "output.json",
        variant=VARIANT,
        tested_commit=TESTED_COMMIT,
        dependency_root=parent._dependency_root(),
    )

    environment = captured["env"]
    assert captured["arguments"][:4] == [
        sys.executable,
        "-P",
        "-S",
        str(parent.CHILD),
    ]
    assert sanitized.isdisjoint(environment)
    pycache_prefix = parent._child_pycache_prefix(tmp_path / "root")
    assert {
        name: value
        for name, value in environment.items()
        if name.upper().startswith("PYTHON")
    } == {
        "PYTHONHASHSEED": "0",
        "PYTHONMALLOC": "pymalloc",
        "PYTHONNOUSERSITE": "1",
        "PYTHONUTF8": "1",
        "PYTHONPYCACHEPREFIX": str(pycache_prefix),
    }
    assert pycache_prefix.is_dir()
    assert not any(pycache_prefix.iterdir())
    dependency_index = captured["arguments"].index("--dependency-root")
    assert Path(captured["arguments"][dependency_index + 1]) == (
        parent._dependency_root()
    )


@pytest.mark.parametrize(
    "status",
    [
        " M namisync/interfaces/web/drain.py\n",
        "?? tests/sitecustomize.py\n",
    ],
)
def test_source_authority_rejects_any_worktree_or_index_dirt(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    parent = _parent_module()
    monkeypatch.setattr(
        parent.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, status, ""
        ),
    )
    with pytest.raises(RuntimeError, match="completely clean"):
        parent._source_authority()


def test_source_authority_rejects_sources_missing_from_tested_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _parent_module()
    results = iter(
        (
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, TESTED_COMMIT + "\n", ""),
            subprocess.CompletedProcess([], 0, "", ""),
        )
    )
    monkeypatch.setattr(
        parent.subprocess,
        "run",
        lambda *_args, **_kwargs: next(results),
    )
    with pytest.raises(RuntimeError, match="source closure is incomplete"):
        parent._source_authority()


def test_source_authority_rejects_clean_hidden_worktree_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _parent_module()
    child = _child_module()
    source_files = child._SOURCE_FILES
    paths = parent._influencing_paths(source_files)
    head_object = "a" * 40
    working_object = "b" * 40

    def run(arguments, **_kwargs):
        command = tuple(arguments[:2])
        if command == ("git", "status"):
            stdout = ""
        elif command == ("git", "rev-parse"):
            stdout = TESTED_COMMIT + "\n"
        elif command == ("git", "ls-tree"):
            stdout = "".join(
                f"100644 blob {head_object}\t{path}\n" for path in paths
            )
        elif command == ("git", "hash-object"):
            stdout = "".join(f"{working_object}\n" for _ in paths)
        else:
            raise AssertionError(f"unexpected Git command: {arguments!r}")
        return subprocess.CompletedProcess(arguments, 0, stdout, "")

    monkeypatch.setattr(parent.subprocess, "run", run)
    monkeypatch.setattr(
        parent, "_tracked_source_files", lambda _commit: source_files
    )
    with pytest.raises(RuntimeError, match="working source differs"):
        parent._source_authority()


def test_source_authority_refuses_changes_between_children(
    custody_run,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _parent_module()
    expected = _artifact_source_authority(custody_run)
    changed = copy.deepcopy(expected)
    changed["source_sha256"] = "f" * 64
    monkeypatch.setattr(parent, "_source_authority", lambda: changed)
    with pytest.raises(RuntimeError, match="changed during runs"):
        parent._verify_source_authority(expected)


def test_retained_instrument_is_hashed_as_a_separate_root(custody_run) -> None:
    assert custody_run["hashes"]["instrument_sha256"] == __import__(
        "hashlib"
    ).sha256(RETAINED.read_bytes()).hexdigest()
