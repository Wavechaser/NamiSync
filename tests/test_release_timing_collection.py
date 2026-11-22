import json

import pytest

from tools.performance import release_timing

REVISION = "a" * 40


def _observation(family):
    if family == "history":
        return {"release_gates_applied": True, "readback": {
            "summary_cold_reader_seconds": 1.7, "summary_warm_reader_seconds": 1.6,
            "item_page_samples_ms": [20.0] * 40, "event_page_samples_ms": [21.0] * 40}}
    return {"passed": True, "measurement_valid": True, "runtime_profile_match": True,
            "archive_scope_clean": True, "tested_commit": REVISION,
            "reliable_and_terminal": {"count": 620, "p95_ms": 10.0, "maximum_ms": 40.0},
            "progress": {"count": 1490, "p95_ms": 45.0, "maximum_ms": 50.0}}


@pytest.fixture
def collection(tmp_path):
    output = tmp_path / "collection"
    runs = []
    for family, case in release_timing.UNITS:
        for child in range(1, release_timing.CHILDREN + 1):
            relative = f"{family}/{case}-{child:02d}.json"
            path = output / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "status": "complete", "family": family, "case": case,
                "environment": {"driver_source": {"dirty": False, "revision": REVISION},
                                "python": "3.15.2 (test)"},
                "observation": _observation(family),
            }), encoding="utf-8")
            runs.append({"family": family, "case": case, "child": child,
                         "exit_code": 0, "report": relative})
    index = {"revision": REVISION, "children": release_timing.CHILDREN, "runs": runs, "finished": "now"}
    (output / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return output


def _rewrite(output, relative, change):
    path = output / relative
    report = json.loads(path.read_text(encoding="utf-8"))
    change(report)
    path.write_text(json.dumps(report), encoding="utf-8")


def test_release_timing_validation_passes_complete_collection(collection):
    verdict = release_timing.validate(collection)
    assert verdict["passed"] is True
    history = verdict["metrics"]["history/release"]
    assert history["children"] == 5 and history["item_page_samples"] == 200
    assert history["summary_max_s"] == 1.7 and history["event_page_max_ms"] == 21.0
    event = verdict["metrics"]["bridge-event/installed"]
    assert event["reliable_and_terminal"] == {"events": 3100, "worst_child_p95_ms": 10.0, "maximum_ms": 40.0}
    assert len(event["report_sha256"]) == 5


@pytest.mark.parametrize(("relative", "change", "row"), [
    ("history/release-02.json",
     lambda r: r["observation"]["readback"]["item_page_samples_ms"].append(1_000.1), "history/release"),
    ("history/release-03.json",
     lambda r: r["observation"]["readback"].update(summary_warm_reader_seconds=3.01), "history/release"),
    ("history/release-04.json",
     lambda r: r["observation"]["readback"].update(event_page_samples_ms=[501.0] * 40), "history/release"),
    ("history/release-01.json",
     lambda r: r["observation"].update(release_gates_applied=False), "history/release"),
    ("history/release-01.json", lambda r: r.update(status="incomplete"), "history/release"),
    ("history/release-05.json",
     lambda r: r["environment"]["driver_source"].update(dirty=True), "history/release"),
    ("bridge-event/installed-02.json",
     lambda r: r["environment"].update(python="3.13.17 (old)"), "bridge-event/installed"),
    ("bridge-event/installed-05.json",
     lambda r: r["observation"].update(measurement_valid=False), "bridge-event/installed"),
    ("bridge-event/installed-03.json",
     lambda r: r["observation"].update(tested_commit="b" * 40), "bridge-event/installed"),
    ("bridge-event/installed-01.json",
     lambda r: r["observation"]["progress"].update(maximum_ms=2_001.0), "bridge-event/installed"),
    ("bridge-event/installed-04.json",
     lambda r: r["observation"]["reliable_and_terminal"].update(p95_ms=101.0), "bridge-event/installed"),
])
def test_release_timing_validation_fails_each_violation(collection, relative, change, row):
    _rewrite(collection, relative, change)
    verdict = release_timing.validate(collection)
    assert verdict["passed"] is False
    assert [name for name, value in verdict["metrics"].items() if not value["passed"]] == [row]


def test_release_timing_validation_rejects_failed_or_unfinished_collection(collection):
    index = json.loads((collection / "index.json").read_text(encoding="utf-8"))
    index["runs"][0]["exit_code"] = 1
    del index["finished"]
    (collection / "index.json").write_text(json.dumps(index), encoding="utf-8")
    verdict = release_timing.validate(collection)
    assert verdict["complete"] is False and verdict["passed"] is False
    assert verdict["metrics"]["history/release"]["problems"] == ["child 1 exit 1"]


def test_release_timing_collection_refuses_dirty_tree(tmp_path, monkeypatch):
    monkeypatch.setattr(release_timing, "_git", lambda *args: " M file.py")
    with pytest.raises(SystemExit, match="not clean"):
        release_timing.collect(tmp_path / "out")
    assert not (tmp_path / "out").exists()
