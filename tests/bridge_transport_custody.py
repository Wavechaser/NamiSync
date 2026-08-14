"""Produce three fresh-process SH-G-8 custody calibration/holdout runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType


REPOSITORY_ROOT = Path(__file__).parents[1]
CHILD = Path(__file__).parent / "interfaces" / "web" / "_bridge_transport_custody.py"
RETAINED = CHILD.with_name("_bridge_retained_memory.py")
MEASUREMENT_KEYS = {
    "adapter_queue_bytes",
    "adapter_queue_objects",
    "replay_queue_bytes",
    "replay_queue_objects",
    "subscriber_queue_bytes",
    "subscriber_queue_objects",
    "terminal_artifact_bytes",
    "terminal_artifact_objects",
    "transport_custody_bytes",
    "transport_custody_objects",
}


def _load_child_contract(
    source_authority: dict[str, object] | None = None,
) -> ModuleType:
    name = "bridge_transport_custody_contract"
    source = CHILD.read_bytes()
    relative = CHILD.relative_to(REPOSITORY_ROOT).as_posix()
    if source_authority is not None and hashlib.sha256(source).hexdigest() != (
        source_authority["source_files"].get(relative)
    ):
        raise RuntimeError("transport-custody child source changed before load")
    module = ModuleType(name)
    module.__file__ = str(CHILD)
    sys.modules[name] = module
    exec(compile(source, str(CHILD), "exec"), module.__dict__)
    if source_authority is not None:
        expected_sources = tuple(
            Path(path) for path in source_authority["source_files"]
        )
        if (
            module._SOURCE_FILES != expected_sources
            or module._RETAINED.resolve() != RETAINED.resolve()
        ):
            raise RuntimeError("transport-custody child source closure drifted")
    return module


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dependency_root() -> Path:
    root = (
        Path(sys.executable).resolve().parent.parent / "Lib" / "site-packages"
    ).resolve()
    if not root.is_dir():
        raise RuntimeError("custody dependency root is not the active venv")
    return root


def _dependency_authority(root: Path | None = None) -> dict[str, object]:
    root = _dependency_root() if root is None else root.resolve()
    if root != _dependency_root():
        raise RuntimeError("custody dependency root is not the active venv")
    package = root / "xxhash"
    extensions = tuple(package.glob("_xxhash*.pyd"))
    if len(extensions) != 1:
        raise RuntimeError("custody xxhash extension set is not exact")
    paths = (package / "__init__.py", package / "version.py", extensions[0])
    if any(not path.is_file() for path in paths):
        raise RuntimeError("custody xxhash dependency is incomplete")
    files = {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in paths
    }
    return {
        "root": str(root),
        "files": files,
        "sha256": _canonical_hash(files),
    }


def _verify_dependency_authority(expected: dict[str, object]) -> None:
    if _dependency_authority(Path(expected["root"])) != expected:
        raise RuntimeError(
            "custody dependency authority changed during runs"
        )


def _runtime_qualifier(runtime: dict[str, object]) -> dict[str, object]:
    normalized = dict(runtime)
    normalized["pycache_prefix"] = "<fresh-per-child>"
    environment = dict(runtime["qualifier_environment"])
    environment["PYTHONPYCACHEPREFIX"] = "<fresh-per-child>"
    normalized["qualifier_environment"] = environment
    return normalized


def _read_child_receipt(
    stdout: str,
    *,
    variant: str,
    tested_commit: str,
) -> dict[str, object]:
    try:
        receipt = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise ValueError("custody child receipt is unreadable") from error
    if (
        type(receipt) is not dict
        or set(receipt)
        != {
            "schema_version",
            "gate",
            "dataset_variant",
            "tested_commit",
            "process_id",
            "evidence_sha256",
            "artifact_sha256",
        }
        or receipt["schema_version"] != 1
        or receipt["gate"] != "SH-G-8 transport custody"
        or receipt["dataset_variant"] != variant
        or receipt["tested_commit"] != tested_commit
        or type(receipt["process_id"]) is not int
        or receipt["process_id"] <= 0
        or any(
            type(receipt[name]) is not str
            or len(receipt[name]) != 64
            or any(character not in "0123456789abcdef" for character in receipt[name])
            for name in ("evidence_sha256", "artifact_sha256")
        )
    ):
        raise ValueError("custody child receipt fields do not match schema")
    return receipt


def _validate_child_receipt(
    receipt: dict[str, object],
    artifact: dict[str, object],
) -> None:
    if (
        receipt["process_id"] != artifact["process_id"]
        or receipt["evidence_sha256"]
        != artifact["hashes"]["evidence_sha256"]
        or receipt["artifact_sha256"] != _canonical_hash(artifact)
    ):
        raise ValueError("custody child receipt does not match its artifact")


def _validate_measurement(
    measurement: object,
    *,
    preterminal: bool,
    strict_shared: bool,
) -> None:
    if (
        type(measurement) is not dict
        or set(measurement) != MEASUREMENT_KEYS
        or any(type(item) is not int or item < 0 for item in measurement.values())
    ):
        raise ValueError("custody byte/object measurements are invalid")
    for prefix in (
        "adapter_queue",
        "replay_queue",
        "subscriber_queue",
        "terminal_artifact",
        "transport_custody",
    ):
        byte_count = measurement[f"{prefix}_bytes"]
        object_count = measurement[f"{prefix}_objects"]
        if (object_count == 0 and byte_count != 0) or (
            object_count > 0 and byte_count < object_count * 16
        ):
            raise ValueError("custody byte/object density is implausible")
    if measurement["transport_custody_bytes"] <= 0:
        raise ValueError("transport custody measurement is missing")
    component_bytes = [
        measurement[f"{role}_queue_bytes"]
        for role in ("replay", "subscriber", "adapter")
    ]
    union_bytes = measurement["transport_custody_bytes"]
    if (
        union_bytes < max(component_bytes)
        or union_bytes > sum(component_bytes)
        or (strict_shared and union_bytes >= sum(component_bytes))
    ):
        raise ValueError("transport custody identity accounting drifted")
    terminal_bytes = measurement["terminal_artifact_bytes"]
    terminal_objects = measurement["terminal_artifact_objects"]
    if preterminal:
        if terminal_bytes != 0 or terminal_objects != 0:
            raise ValueError("preterminal custody contains terminal artifacts")
    elif (
        terminal_bytes <= 0
        or terminal_objects <= 0
        or union_bytes >= terminal_bytes
    ):
        raise ValueError("terminal-result path-cut witness is invalid")


def _read_run_artifact(
    path: Path,
    contract: ModuleType,
    *,
    variant: str,
    source_authority: dict[str, object],
    dependency_authority: dict[str, object],
    expected_pycache_prefix: Path,
) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"custody run artifact is unreadable: {path.name}") from error
    _validate_run_artifact(
        value,
        contract,
        variant=variant,
        source_authority=source_authority,
        dependency_authority=dependency_authority,
        expected_pycache_prefix=expected_pycache_prefix,
    )
    return value


def _validate_run_artifact(
    value: object,
    contract: ModuleType,
    *,
    variant: str,
    source_authority: dict[str, object],
    dependency_authority: dict[str, object],
    expected_pycache_prefix: Path,
    expected_source_root: Path | None = None,
    expected_python: str | None = None,
    expected_executable: Path | None = None,
) -> None:
    if set(source_authority) != {
        "tested_commit",
        "source_files",
        "source_sha256",
        "instrument_sha256",
    }:
        raise ValueError("custody source authority fields do not match schema")
    if type(value) is not dict:
        raise ValueError("custody run artifact must be an object")
    required = {
        "schema_version",
        "gate",
        "corpus_version",
        "dataset_variant",
        "tested_commit",
        "headroom_policy",
        "process_id",
        "module_origins",
        "dependency_authority",
        "runtime",
        "hashes",
        "structural_facts",
        "ordinary",
        "maximum_no_gap",
    }
    if set(value) != required:
        raise ValueError("custody run artifact fields do not match schema")
    if value["schema_version"] != 1:
        raise ValueError("custody run artifact schema version is unsupported")
    if value["gate"] != "SH-G-8 transport custody":
        raise ValueError("custody run artifact gate is invalid")
    if value["corpus_version"] != contract.CORPUS_VERSION:
        raise ValueError("custody run artifact corpus version is invalid")
    if value["dataset_variant"] != variant:
        raise ValueError("custody run artifact dataset variant is invalid")
    if value["tested_commit"] != source_authority.get("tested_commit"):
        raise ValueError("custody run artifact tested commit is invalid")
    if value["headroom_policy"] != contract.HEADROOM_POLICY:
        raise ValueError("custody run artifact headroom policy drifted")
    structural_facts = contract._structural_facts(variant)
    if value["structural_facts"] != structural_facts:
        raise ValueError("custody run artifact structural facts drifted")
    if type(value["process_id"]) is not int or value["process_id"] <= 0:
        raise ValueError("custody run artifact process id is invalid")
    if (
        type(dependency_authority) is not dict
        or set(dependency_authority) != {"root", "files", "sha256"}
        or type(dependency_authority["root"]) is not str
        or type(dependency_authority["files"]) is not dict
        or type(dependency_authority["sha256"]) is not str
        or value["dependency_authority"] != dependency_authority
        or dependency_authority["sha256"]
        != _canonical_hash(dependency_authority["files"])
    ):
        raise ValueError("custody run dependency authority drifted")
    dependency_files = dependency_authority["files"]
    extension_files = (
        {
            name
            for name in dependency_files
            if name.startswith("xxhash/_xxhash") and name.endswith(".pyd")
        }
        if type(dependency_files) is dict
        else set()
    )
    if (
        type(dependency_files) is not dict
        or len(extension_files) != 1
        or set(dependency_files)
        != {"xxhash/__init__.py", "xxhash/version.py"} | extension_files
        or any(
            type(digest) is not str
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            for digest in dependency_files.values()
        )
    ):
        raise ValueError("custody run dependency manifest is invalid")
    source_root = (
        contract._ROOT
        if expected_source_root is None
        else expected_source_root
    )
    expected_origins = {
        name: str((source_root / relative).resolve())
        for name, relative in contract._MODULE_PATHS.items()
    }
    extension = next(
        name for name in dependency_files if name.startswith("xxhash/_xxhash")
    )
    dependency_root = Path(dependency_authority["root"])
    expected_origins.update(
        {
            "xxhash": str((dependency_root / "xxhash/__init__.py").resolve()),
            "xxhash.version": str(
                (dependency_root / "xxhash/version.py").resolve()
            ),
            "xxhash._xxhash": str((dependency_root / extension).resolve()),
        }
    )
    if value["module_origins"] != expected_origins:
        raise ValueError("custody run module origins drifted")

    runtime = value["runtime"]
    hashes = value["hashes"]
    if type(runtime) is not dict or type(hashes) is not dict:
        raise ValueError("custody run runtime/hash evidence is invalid")
    if set(hashes) != {
        "runtime_sha256",
        "runtime_qualifier_sha256",
        "source_sha256",
        "source_files",
        "corpus_sha256",
        "instrument_sha256",
        "evidence_sha256",
    }:
        raise ValueError("custody run hash fields do not match schema")
    if hashes["runtime_sha256"] != _canonical_hash(runtime):
        raise ValueError("custody run runtime hash does not match")
    if hashes["runtime_qualifier_sha256"] != _canonical_hash(
        _runtime_qualifier(runtime)
    ):
        raise ValueError("custody run runtime qualifier hash does not match")
    if hashes["corpus_sha256"] != _canonical_hash(structural_facts):
        raise ValueError("custody run corpus hash does not match")
    if set(runtime) != {
        "python",
        "version_info",
        "implementation",
        "platform",
        "executable",
        "pointer_bits",
        "py_debug",
        "with_pymalloc_config",
        "allocator_predicate",
        "python_hash_seed",
        "python_malloc",
        "no_site",
        "safe_path",
        "pycache_prefix",
        "pycache_prefix_role",
        "dependency_root",
        "optimize",
        "dev_mode",
        "tracemalloc",
        "qualifier_environment",
        "allocation_method",
    }:
        raise ValueError("custody run runtime fields do not match schema")
    version_info = runtime["version_info"]
    if (
        runtime["implementation"] != "CPython"
        or runtime["python"]
        != (contract.sys.version if expected_python is None else expected_python)
        or type(version_info) is not list
        or len(version_info) != 5
        or version_info[:2] != [3, 13]
        or version_info[3:] != ["final", 0]
        or runtime["pointer_bits"] != 64
        or runtime["py_debug"] != 0
        or not runtime["platform"].startswith("Windows-")
        or runtime["executable"]
        != str(
            (
                Path(sys.executable)
                if expected_executable is None
                else expected_executable
            ).resolve()
        )
        or runtime["with_pymalloc_config"] is not None
        or runtime["allocator_predicate"]
        != "explicit-pymalloc-on-qualified-Windows-CPython"
        or runtime["python_hash_seed"] != "0"
        or runtime["python_malloc"] != "pymalloc"
        or runtime["no_site"] != 1
        or runtime["safe_path"] is not True
        or runtime["pycache_prefix"]
        != str(expected_pycache_prefix.resolve())
        or runtime["pycache_prefix_role"]
        != "fresh-empty-per-child-outside-source-tree"
        or runtime["dependency_root"] != dependency_authority["root"]
        or runtime["optimize"] != 0
        or runtime["dev_mode"] is not False
        or runtime["tracemalloc"] is not False
        or runtime["qualifier_environment"]
        != {
            "PYTHONHASHSEED": "0",
            "PYTHONMALLOC": "pymalloc",
            "PYTHONNOUSERSITE": "1",
            "PYTHONUTF8": "1",
            "PYTHONPYCACHEPREFIX": str(expected_pycache_prefix.resolve()),
        }
        or runtime["allocation_method"] != contract.ALLOCATION_METHOD
    ):
        raise ValueError(
            "custody run runtime is outside the frozen qualifier: "
            f"{runtime!r}"
        )
    source_files = hashes["source_files"]
    if type(source_files) is not dict or hashes["source_sha256"] != _canonical_hash(
        source_files
    ):
        raise ValueError("custody run source manifest does not match")
    if source_files != source_authority.get("source_files"):
        raise ValueError("custody run source files do not match authority")
    if hashes["source_sha256"] != source_authority.get("source_sha256"):
        raise ValueError("custody run source hash does not match authority")
    if hashes["instrument_sha256"] != source_authority.get(
        "instrument_sha256"
    ):
        raise ValueError("custody run instrument hash does not match")

    ordinary = value["ordinary"]
    maximum = value["maximum_no_gap"]
    if type(ordinary) is not dict or type(maximum) is not dict:
        raise ValueError("custody run fixtures are invalid")
    if hashes["evidence_sha256"] != _canonical_hash(
        {"ordinary": ordinary, "maximum_no_gap": maximum}
    ):
        raise ValueError("custody run evidence hash does not match")
    if set(ordinary) != {
        "emissions",
        "root_container_type",
        "delivered",
        "no_gap",
        "progress_per_task",
        "ordering",
        "observed_checkpoint_peak",
        "custody_sampling",
        "ordinary_quiescent_peak",
        "terminal_path_cut_witness",
    } or set(maximum) != {
        "emissions",
        "root_container_type",
        "no_gap",
        "queue_lengths",
        "observed_queue_high_water",
        "custody_sampling",
        "custody",
        "cleanup_delivery",
    }:
        raise ValueError("custody fixture fields do not match schema")
    if ordinary["root_container_type"] != "collections.deque" or maximum[
        "root_container_type"
    ] != "collections.deque":
        raise ValueError("custody roots are not built-in deques")
    if ordinary["custody_sampling"] != (
        "60 exact-body producer-quiescent checkpoints plus terminal "
        "transport projection"
    ) or maximum["custody_sampling"] != (
        "exact producer-quiescent maximum no-Gap shape"
    ):
        raise ValueError("custody sampling description drifted")
    if ordinary.get("emissions") != {"progress": 6_000, "outcomes": 600}:
        raise ValueError("ordinary custody emission facts drifted")
    if ordinary.get("delivered") != {
        "progress": 240,
        "outcomes": 600,
        "terminal_events": 4,
        "terminal_records": 4,
    }:
        raise ValueError("ordinary custody delivery facts drifted")
    if ordinary.get("progress_per_task") != [60, 60, 60, 60]:
        raise ValueError("ordinary custody progress cadence drifted")
    if ordinary.get("ordering") != {
        "event_sequences_strict": True,
        "reliable_ids_exact": True,
        "terminal_order_exact": True,
    }:
        raise ValueError("ordinary custody ordering drifted")
    if ordinary.get("no_gap") is not True:
        raise ValueError("ordinary custody run contains a Gap")
    if maximum.get("emissions") != {"outcomes": 516}:
        raise ValueError("maximum custody emission facts drifted")
    exact_shape = {
        "replay": [128, 128, 128, 128],
        "subscriber": [64, 64, 64, 64],
        "adapter": [64, 64, 64, 64],
    }
    if maximum.get("queue_lengths") != exact_shape:
        raise ValueError("maximum custody queue shape drifted")
    if maximum.get("no_gap") is not True:
        raise ValueError("maximum custody run contains a Gap")
    if maximum.get("cleanup_delivery") != {
        "outcomes": 516,
        "outcomes_per_task": [129, 129, 129, 129],
        "terminal_events": 4,
        "terminal_records": 4,
        "terminal_order_exact": True,
        "failed_state_headline_records": 4,
    }:
        raise ValueError("maximum custody cleanup delivery drifted")
    for fixture, field in (
        (ordinary, "observed_checkpoint_peak"),
        (maximum, "observed_queue_high_water"),
    ):
        queue_high_water = fixture.get(field)
        if type(queue_high_water) is not dict or set(queue_high_water) != {
            "replay",
            "subscriber",
            "adapter",
        }:
            raise ValueError("custody queue high-water schema drifted")
        for role, expected_maximum in (
            ("replay", 128),
            ("subscriber", 64),
            ("adapter", 64),
        ):
            evidence = queue_high_water[role]
            if (
                type(evidence) is not dict
                or set(evidence) != {"per_queue", "maximum"}
                or type(evidence["per_queue"]) is not list
                or len(evidence["per_queue"]) != 4
                or any(
                    type(item) is not int or not 0 <= item <= expected_maximum
                    for item in evidence["per_queue"]
                )
                or evidence["maximum"] != max(evidence["per_queue"])
            ):
                raise ValueError("custody queue high-water evidence drifted")
    if maximum["observed_queue_high_water"] != {
        role: {"per_queue": values, "maximum": max(values)}
        for role, values in exact_shape.items()
    }:
        raise ValueError("maximum custody high-water shape drifted")
    if ordinary["observed_checkpoint_peak"] != {
        "replay": {"per_queue": [128, 128, 128, 128], "maximum": 128},
        "subscriber": {"per_queue": [0, 0, 0, 0], "maximum": 0},
        "adapter": {"per_queue": [4, 4, 4, 4], "maximum": 4},
    }:
        raise ValueError("ordinary custody checkpoint shape drifted")
    for fixture, field, strict_shared in (
        (ordinary, "ordinary_quiescent_peak", False),
        (maximum, "custody", True),
    ):
        measurement = fixture.get(field)
        _validate_measurement(
            measurement,
            preterminal=True,
            strict_shared=strict_shared,
        )
    witness = ordinary.get("terminal_path_cut_witness")
    if (
        type(witness) is not dict
        or set(witness)
        != {
            "authority",
            "transport_result_exclusion_exercised",
            "measurement",
        }
        or witness["authority"] != "BR-G-45-nonnormative"
        or witness["transport_result_exclusion_exercised"] is not True
    ):
        raise ValueError("terminal-result path-cut witness schema drifted")
    _validate_measurement(
        witness["measurement"],
        preterminal=False,
        strict_shared=False,
    )


def _validate_archived_run_artifact(
    value: object,
    contract: ModuleType,
    *,
    variant: str,
    source_authority: dict[str, object],
    dependency_authority: dict[str, object],
    expected_pycache_prefix: Path,
) -> None:
    if type(value) is not dict or type(value.get("module_origins")) is not dict:
        raise ValueError("archived custody run artifact is invalid")
    module_origins = value["module_origins"]
    roots: set[Path] = set()
    for name, relative in contract._MODULE_PATHS.items():
        origin = module_origins.get(name)
        if type(origin) is not str:
            raise ValueError("archived custody module origin is invalid")
        root = Path(origin)
        for _ in Path(relative).parts:
            root = root.parent
        roots.add(root.resolve())
    if len(roots) != 1:
        raise ValueError("archived custody source roots disagree")

    runtime = value.get("runtime")
    if type(runtime) is not dict or type(runtime.get("python")) is not str:
        raise ValueError("archived custody runtime is invalid")
    dependency_root = Path(dependency_authority["root"])
    expected_executable = dependency_root.parent.parent / "Scripts" / "python.exe"
    _validate_run_artifact(
        value,
        contract,
        variant=variant,
        source_authority=source_authority,
        dependency_authority=dependency_authority,
        expected_pycache_prefix=expected_pycache_prefix,
        expected_source_root=next(iter(roots)),
        expected_python=runtime["python"],
        expected_executable=expected_executable,
    )


def _run_child(
    root: Path,
    output: Path,
    *,
    variant: str,
    tested_commit: str,
    dependency_root: Path,
) -> subprocess.CompletedProcess[str]:
    pycache_prefix = _child_pycache_prefix(root)
    try:
        pycache_prefix.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise RuntimeError("custody child pycache prefix enters source tree")
    pycache_prefix.mkdir(parents=False, exist_ok=False)
    if any(pycache_prefix.iterdir()):
        raise RuntimeError("custody child pycache prefix is not fresh and empty")
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith("PYTHON")
    }
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "PYTHONMALLOC": "pymalloc",
            "PYTHONNOUSERSITE": "1",
            "PYTHONUTF8": "1",
            "PYTHONPYCACHEPREFIX": str(pycache_prefix),
        }
    )
    return subprocess.run(
        [
            sys.executable,
            "-P",
            "-S",
            str(CHILD),
            "--root",
            str(root),
            "--output",
            str(output),
            "--variant",
            variant,
            "--tested-commit",
            tested_commit,
            "--dependency-root",
            str(dependency_root.resolve()),
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


def _child_pycache_prefix(root: Path) -> Path:
    return (root.parent / f"{root.name}-pycache").resolve()


def _measurement_maxima(runs: list[dict[str, object]]) -> dict[str, object]:
    ordinary_keys = tuple(runs[0]["ordinary"]["ordinary_quiescent_peak"])
    maximum_keys = tuple(runs[0]["maximum_no_gap"]["custody"])
    return {
        "ordinary_quiescent_peak": {
            key: max(
                run["ordinary"]["ordinary_quiescent_peak"][key]
                for run in runs
            )
            for key in ordinary_keys
        },
        "maximum_no_gap_custody": {
            key: max(run["maximum_no_gap"]["custody"][key] for run in runs)
            for key in maximum_keys
        },
    }


def _influencing_paths(source_files: tuple[Path, ...]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *(path.as_posix() for path in source_files),
                RETAINED.relative_to(REPOSITORY_ROOT).as_posix(),
            }
        )
    )


def _tracked_source_files(tested_commit: str) -> tuple[Path, ...]:
    tree = subprocess.run(
        [
            "git",
            "ls-tree",
            "-r",
            "--full-tree",
            "--name-only",
            tested_commit,
            "--",
            "namisync",
        ],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    )
    project = {
        path
        for path in tree.stdout.splitlines()
        if path.startswith("namisync/") and path.endswith(".py")
    }
    required = {
        CHILD.relative_to(REPOSITORY_ROOT).as_posix(),
        Path(__file__).resolve().relative_to(REPOSITORY_ROOT).as_posix(),
    }
    paths = tuple(Path(path) for path in sorted(project | required))
    if not project or len(paths) != len(project) + len(required):
        raise RuntimeError("custody tested source closure is incomplete")
    return paths


def _require_head_blob_match(
    paths: tuple[str, ...],
    tested_commit: str,
) -> None:
    tree = subprocess.run(
        [
            "git",
            "ls-tree",
            "-r",
            "--full-tree",
            tested_commit,
            "--",
            *paths,
        ],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    )
    head_paths = []
    head_objects = []
    for line in tree.stdout.splitlines():
        try:
            metadata, path = line.split("\t", 1)
            _mode, object_type, object_id = metadata.split()
        except ValueError as error:
            raise RuntimeError("custody HEAD blob manifest is malformed") from error
        if (
            object_type != "blob"
            or len(object_id) != 40
            or any(character not in "0123456789abcdef" for character in object_id)
        ):
            raise RuntimeError("custody HEAD blob manifest is malformed")
        head_paths.append(path)
        head_objects.append(object_id)
    if tuple(head_paths) != paths:
        raise RuntimeError("custody evidence source set does not match tested commit")

    working = subprocess.run(
        ["git", "hash-object", "--stdin-paths"],
        cwd=REPOSITORY_ROOT,
        input="".join(f"{path}\n" for path in paths),
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    )
    working_objects = tuple(working.stdout.splitlines())
    if (
        len(working_objects) != len(paths)
        or any(
            len(object_id) != 40
            or any(
                character not in "0123456789abcdef"
                for character in object_id
            )
            for object_id in working_objects
        )
    ):
        raise RuntimeError("custody working blob manifest is malformed")
    if working_objects != tuple(head_objects):
        raise RuntimeError("custody working source differs from tested commit")


def _source_authority() -> dict[str, object]:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    )
    if status.stdout:
        raise RuntimeError(
            "custody evidence requires a completely clean worktree and index"
        )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    ).stdout.strip()
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise RuntimeError("custody evidence could not resolve a full tested commit")
    source_paths = _tracked_source_files(commit)
    _require_head_blob_match(_influencing_paths(source_paths), commit)
    source_files = {
        path.as_posix(): hashlib.sha256(
            (REPOSITORY_ROOT / path).read_bytes()
        ).hexdigest()
        for path in source_paths
    }
    return {
        "tested_commit": commit,
        "source_files": source_files,
        "source_sha256": _canonical_hash(source_files),
        "instrument_sha256": hashlib.sha256(
            RETAINED.read_bytes()
        ).hexdigest(),
    }


def _verify_source_authority(expected: dict[str, object]) -> None:
    if _source_authority() != expected:
        raise RuntimeError("custody evidence source authority changed during runs")


def _require_authoritative_parent() -> None:
    if not (
        sys.flags.isolated == 1
        and sys.flags.ignore_environment == 1
        and sys.flags.no_site == 1
        and sys.flags.safe_path is True
    ):
        raise RuntimeError(
            "custody evidence parent must be launched with Python -I -S"
        )


def build_dataset(kind: str, temporary_root: Path) -> dict[str, object]:
    _require_authoritative_parent()
    if kind not in {"calibration", "holdout"}:
        raise ValueError("dataset kind must be calibration or holdout")
    variant = "calibration-a" if kind == "calibration" else "holdout-b"
    source_authority = _source_authority()
    dependency_authority = _dependency_authority()
    contract = _load_child_contract(source_authority)
    tested_commit = source_authority["tested_commit"]
    runs = []
    receipts = []
    for index in range(3):
        run_root = temporary_root / f"run-{index + 1}"
        output = temporary_root / f"run-{index + 1}.json"
        _verify_source_authority(source_authority)
        _verify_dependency_authority(dependency_authority)
        completed = _run_child(
            run_root,
            output,
            variant=variant,
            tested_commit=tested_commit,
            dependency_root=Path(dependency_authority["root"]),
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"custody child {index + 1} failed with {completed.returncode}: "
                f"{completed.stdout}{completed.stderr}"
            )
        _verify_source_authority(source_authority)
        _verify_dependency_authority(dependency_authority)
        receipt = _read_child_receipt(
            completed.stdout,
            variant=variant,
            tested_commit=tested_commit,
        )
        artifact = _read_run_artifact(
            output,
            contract,
            variant=variant,
            source_authority=source_authority,
            dependency_authority=dependency_authority,
            expected_pycache_prefix=_child_pycache_prefix(run_root),
        )
        _validate_child_receipt(receipt, artifact)
        runs.append(artifact)
        receipts.append(receipt)

    process_ids = [run["process_id"] for run in runs]
    if len(set(process_ids)) != 3:
        raise RuntimeError("custody dataset did not use three fresh child processes")
    stable_hash_names = (
        "runtime_qualifier_sha256",
        "source_sha256",
        "corpus_sha256",
        "instrument_sha256",
    )
    for name in stable_hash_names:
        if len({run["hashes"][name] for run in runs}) != 1:
            raise RuntimeError(f"custody run {name} values are inconsistent")
    _verify_source_authority(source_authority)
    _verify_dependency_authority(dependency_authority)

    first = runs[0]
    return {
        "schema_version": 1,
        "gate": "SH-G-8 transport custody",
        "dataset_kind": kind,
        "dataset_variant": variant,
        "tested_commit": tested_commit,
        "dependency_authority": dependency_authority,
        "corpus_version": contract.CORPUS_VERSION,
        "run_count": 3,
        "headroom_policy": contract.HEADROOM_POLICY,
        "hashes": first["hashes"],
        "structural_facts": contract._structural_facts(variant),
        "measurement_maxima": _measurement_maxima(runs),
        "run_receipts": receipts,
        "runs": runs,
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("calibration", "holdout"))
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    with tempfile.TemporaryDirectory(prefix="namisync-sh-g-8-custody-") as raw:
        result = build_dataset(arguments.kind, Path(raw))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "dataset_kind": result["dataset_kind"],
                "measurement_maxima": result["measurement_maxima"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
