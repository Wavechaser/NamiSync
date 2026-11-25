"""The v0.1.0 fixture producer refuses unsafe output and contains its children.

No released executable runs here and the live data root is never touched: a
temporary folder stands in for it, and a stub script stands in for the CLI.
"""

from __future__ import annotations

import _winapi
import json
import os
from pathlib import Path
import sys
import time
from typing import Callable

import pytest

from tools.fixtures import v0_1_0_pair as producer


STUB = """\
import json, os, sys
from pathlib import Path

Path("received.json").write_text(
    json.dumps({"LOCALAPPDATA": os.environ.get("LOCALAPPDATA"), "argv": sys.argv[1:]}),
    encoding="utf-8",
)
if "--leak" in sys.argv:
    (Path(os.environ["LOCALAPPDATA"]) / "leak-probe").mkdir()
"""


@pytest.fixture
def live(tmp_path: Path) -> Path:
    root = tmp_path / "Local" / "NamiSync"
    root.mkdir(parents=True)
    return root


def _junction(live: Path, tmp_path: Path) -> Path:
    alias = tmp_path / "alias"
    _winapi.CreateJunction(str(live), str(alias))
    return alias


ALIASES: dict[str, Callable[[Path, Path], Path]] = {
    "exact": lambda live, _: live,
    "case": lambda live, _: Path(str(live).swapcase()),
    "trailing-separator": lambda live, _: Path(str(live) + "\\"),
    "inside": lambda live, _: live / "fresh",
    "case-inside": lambda live, _: Path(str(live).upper()) / "fresh",
    "dot-dot": lambda live, _: live / "other" / ".." / "fresh",
    "verbatim": lambda live, _: Path("\\\\?\\" + str(live)),
    "verbatim-inside": lambda live, _: Path("\\\\?\\" + str(live)) / "fresh",
    "junction": _junction,
    "junction-inside": lambda live, tmp_path: _junction(live, tmp_path) / "fresh",
}


@pytest.mark.parametrize("alias", sorted(ALIASES))
def test_output_at_or_inside_the_live_root_is_refused(
    live: Path, tmp_path: Path, alias: str
) -> None:
    output = ALIASES[alias](live, tmp_path)
    with pytest.raises(producer.Refused, match="the live data root"):
        producer.admit_output(output, live=live)
    assert not (live / "fresh").exists()


def test_output_inside_the_live_root_through_an_admin_share_is_refused(
    live: Path,
) -> None:
    share = Path("\\\\localhost\\" + str(live).replace(":", "$", 1))
    if not share.exists():
        pytest.skip("the \\\\localhost administrative share is not reachable")
    with pytest.raises(producer.Refused, match="the live data root"):
        producer.admit_output(share / "fresh", live=live)


def test_spelling_still_refuses_when_the_live_root_is_absent(tmp_path: Path) -> None:
    live = tmp_path / "Local" / "NamiSync"
    with pytest.raises(producer.Refused, match="the live data root"):
        producer.admit_output(Path(str(live).upper()) / "fresh", live=live)


def test_output_beside_the_live_root_is_admitted(live: Path) -> None:
    for output in (live.parent / "NamiSync-Development", live.parent / "fresh"):
        assert producer.admit_output(output, live=live) == output.resolve()
        assert not output.exists()


def test_output_inside_tests_assets_is_refused(live: Path) -> None:
    output = producer.REPOSITORY / "tests" / "assets" / "never-created"
    with pytest.raises(producer.Refused, match="tests/assets"):
        producer.admit_output(output, live=live)
    assert not output.exists()


def test_nonempty_output_is_refused(live: Path, tmp_path: Path) -> None:
    output = tmp_path / "used"
    output.mkdir()
    (output / "earlier.txt").write_text("earlier", encoding="utf-8")
    with pytest.raises(producer.Refused, match="not empty"):
        producer.admit_output(output, live=live)


def _stub_run(tmp_path: Path) -> producer.Run:
    stub = tmp_path / "stub.py"
    stub.write_text(STUB, encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    return producer.Run(output, stub, launcher=(sys.executable,))


def test_child_gets_the_substitute_localappdata_and_both_database_flags(
    tmp_path: Path,
) -> None:
    parent_before = dict(os.environ)
    run = _stub_run(tmp_path)

    assert run.invoke("inventory", ["inventory", "root"], expected=0) == 0

    received = json.loads((run.output / "received.json").read_text(encoding="utf-8"))
    assert received["LOCALAPPDATA"] == str(run.sandbox)
    assert dict(os.environ) == parent_before
    assert received["argv"] == [
        "inventory",
        "root",
        "--database",
        str(run.ledger),
        "--history-database",
        str(run.history),
    ]
    assert run.steps[-1]["command"] == [
        "namisync.exe",
        "inventory",
        "root",
        "--database",
        "<OUTPUT>\\data\\ledger.db",
        "--history-database",
        "<OUTPUT>\\data\\history.db",
    ]


@pytest.mark.parametrize("answer", (None, "execute"), ids=("no-prompt", "awaiting-prompt"))
def test_a_child_that_stalls_is_killed_at_the_step_timeout(
    tmp_path: Path, answer: str | None,
) -> None:
    # With an answer the producer first blocks reading for the prompt, which
    # the stalled child never prints.
    run = _stub_run(tmp_path)
    run.executable.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    run.step_timeout = 1.0
    started = time.monotonic()
    with pytest.raises(producer.Refused, match="stall exceeded 1.0 s"):
        run.invoke("stall", [], expected=0, answer=answer)
    assert time.monotonic() - started < 20
    assert (run.logs / "01-stall.txt").exists()


def test_child_writing_into_the_substitute_localappdata_refuses_the_run(
    tmp_path: Path,
) -> None:
    run = _stub_run(tmp_path)
    with pytest.raises(producer.Refused, match="substitute LOCALAPPDATA"):
        run.invoke("leak", ["--leak"], expected=0)
    assert (run.sandbox / "leak-probe").is_dir()
