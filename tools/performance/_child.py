"""Bound one selected measurement child and retain its raw failure log."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4


_REPOSITORY = Path(__file__).resolve().parents[2]
_WEB_TESTS = _REPOSITORY / "tests" / "interfaces" / "web"
if str(_WEB_TESTS) not in sys.path:
    sys.path.insert(0, str(_WEB_TESTS))

from _headed_native import (  # noqa: E402
    clean_child_environment,
    scenario_deadline,
    start_headed_process,
    terminate_process_tree,
    wait_for_process,
)


def run_child(
    module: str,
    arguments: list[str],
    *,
    output: Path,
    installed_root: Path | None,
    timeout_seconds: float = 300,
) -> dict[str, object]:
    raw_root = output.with_name(f"{output.stem}-{uuid4().hex}-raw")
    raw_root.mkdir()
    receipt_path = raw_root / "receipt.json"
    log_path = raw_root / "child.log"
    environment = clean_child_environment()
    source_path = str(_REPOSITORY)
    environment["PYTHONPATH"] = (
        f"{installed_root.resolve()};{source_path}"
        if installed_root is not None else source_path
    )
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [
        str(Path(sys.executable).resolve()), "-m", module,
        *arguments, "--output", str(receipt_path),
    ]
    deadline = scenario_deadline(timeout_seconds)
    process = None
    try:
        with log_path.open("xb") as log:
            try:
                process = start_headed_process(
                    command, cwd=raw_root, environment=environment,
                    deadline=deadline, stdout=log, stderr=log,
                )
                completed = wait_for_process(process, deadline=deadline)
            finally:
                if process is not None:
                    if process.poll() is None:
                        terminate_process_tree(process, deadline=deadline)
                    else:
                        process.close_job()
    except Exception as error:
        raise RuntimeError(f"{error}; raw evidence: {raw_root}") from error
    if completed.returncode != 0:
        raise RuntimeError(
            f"measurement child exited {completed.returncode}; raw log: {log_path}"
        )
    if not receipt_path.is_file():
        raise RuntimeError(f"measurement child omitted its receipt; raw log: {log_path}")
    try:
        receipt = json.loads(receipt_path.read_bytes())
    except (OSError, ValueError) as error:
        raise RuntimeError(f"measurement child receipt is invalid; raw log: {log_path}") from error
    if type(receipt) is not dict:
        raise RuntimeError(f"measurement child receipt is not an object; raw log: {log_path}")
    receipt["raw_log"] = str(log_path)
    return receipt
