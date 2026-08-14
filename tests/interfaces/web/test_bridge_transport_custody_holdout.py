"""Committed SH-G-8 transport-custody holdout acceptance witness."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


FROZEN_VALIDATOR = Path(__file__).with_name(
    "test_bridge_transport_custody.py"
)
HOLDOUT = Path(__file__).with_name("sh_g_8_transport_holdout.json")
REPOSITORY_ROOT = Path(__file__).parents[3]

_HOLDOUT_SHA256 = (
    "96ec4003c74fa5ca2800ae2ec5672d3c509ceaaf79bca23ad0c864112e9d32d1"
)
_TESTED_COMMIT = "455df3a6fdc1307af140bf91b1dea95774fb36fe"


def _frozen_validator():
    name = "bridge_transport_custody_frozen_acceptance"
    specification = importlib.util.spec_from_file_location(
        name, FROZEN_VALIDATOR
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def test_committed_holdout_passes_frozen_transport_custody_ceiling() -> None:
    frozen = _frozen_validator()
    parent = frozen._parent_module()
    child = frozen._child_module()
    artifact_bytes = HOLDOUT.read_bytes()
    artifact = json.loads(artifact_bytes)

    assert hashlib.sha256(artifact_bytes).hexdigest() == _HOLDOUT_SHA256
    assert artifact["dataset_kind"] == "holdout"
    assert artifact["dataset_variant"] == "holdout-b"
    assert artifact["tested_commit"] == _TESTED_COMMIT
    assert artifact["run_count"] == 3
    assert [run["process_id"] for run in artifact["runs"]] == [
        37_508,
        44_384,
        44_596,
    ]

    result = frozen._validate_holdout_acceptance(parent, child, artifact)
    assert result == {
        "ceiling_bytes": 1_966_080,
        "ordinary_transport_custody_bytes": 1_351_794,
        "maximum_transport_custody_bytes": 1_513_014,
    }
    assert result["ordinary_transport_custody_bytes"] < result[
        "ceiling_bytes"
    ]
    assert result["maximum_transport_custody_bytes"] < result[
        "ceiling_bytes"
    ]

    def keys(value: object):
        if isinstance(value, dict):
            for key, child_value in value.items():
                yield str(key)
                yield from keys(child_value)
        elif isinstance(value, list):
            for child_value in value:
                yield from keys(child_value)

    raw_keys = set(keys(artifact))
    assert "acceptance" not in raw_keys
    assert "passed" not in raw_keys
    assert "ceiling_bytes" not in raw_keys
    assert "limit_bytes" not in raw_keys


def test_custody_evidence_byte_authority_is_explicitly_pinned() -> None:
    paths = [
        "tests/bridge_transport_custody.py",
        "tests/interfaces/web/test_bridge_transport_custody.py",
        "tests/interfaces/web/test_bridge_transport_custody_holdout.py",
        "tests/interfaces/web/sh_g_8_transport_calibration.json",
        "tests/interfaces/web/sh_g_8_transport_ceiling.json",
        "tests/interfaces/web/sh_g_8_transport_holdout.json",
    ]
    completed = subprocess.run(
        ["git", "check-attr", "eol", "--", *paths],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    )
    expected = {
        paths[3]: "crlf",
        paths[5]: "crlf",
    }
    assert completed.stdout.splitlines() == [
        f"{path}: eol: {expected.get(path, 'lf')}" for path in paths
    ]
