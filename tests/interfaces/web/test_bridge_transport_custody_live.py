"""Current-source drift guard for SH-G-8 transport custody."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


FROZEN_VALIDATOR = Path(__file__).with_name(
    "test_bridge_transport_custody.py"
)

_CEILING_BYTES = 1_966_080


def _frozen_validator():
    name = "bridge_transport_custody_live_guard"
    specification = importlib.util.spec_from_file_location(
        name, FROZEN_VALIDATOR
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def test_current_source_transport_custody_stays_within_frozen_ceiling(
    tmp_path: Path,
) -> None:
    frozen = _frozen_validator()
    parent = frozen._parent_module()
    child = frozen._child_module()
    output = tmp_path / "current-source-custody.json"
    completed = parent._run_child(
        tmp_path / "fixture",
        output,
        variant=frozen.VARIANT,
        tested_commit=frozen.TESTED_COMMIT,
        dependency_root=parent._dependency_root(),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    artifact = json.loads(output.read_text(encoding="utf-8"))
    receipt = parent._read_child_receipt(
        completed.stdout,
        variant=frozen.VARIANT,
        tested_commit=frozen.TESTED_COMMIT,
    )
    parent._validate_child_receipt(receipt, artifact)
    parent._validate_run_artifact(
        artifact,
        child,
        variant=frozen.VARIANT,
        source_authority=frozen._artifact_source_authority(artifact),
        dependency_authority=frozen._artifact_dependency_authority(artifact),
        expected_pycache_prefix=frozen._artifact_pycache_prefix(artifact),
    )

    contract, _calibration = frozen._load_transport_custody_ceiling_contract(
        parent, child
    )
    ceiling = contract["ceiling"]["transport_custody_bytes"]
    assert ceiling == _CEILING_BYTES
    measurements = {
        "ordinary": artifact["ordinary"]["ordinary_quiescent_peak"][
            "transport_custody_bytes"
        ],
        "maximum-no-Gap": artifact["maximum_no_gap"]["custody"][
            "transport_custody_bytes"
        ],
    }
    for name, measured in measurements.items():
        assert measured <= ceiling, (
            f"{name} current-source transport custody {measured:,} bytes "
            f"exceeds the frozen {ceiling:,}-byte ceiling"
        )
