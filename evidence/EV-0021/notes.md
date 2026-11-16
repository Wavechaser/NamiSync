Notes for "AB-2/AB-10 incident trace (2026-09-27)": text files chosen from `build/incident-trace-20260927`, `build/trace-20260927/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/incident-trace-20260927/findings.md`

# Ablation incident tracing — 2026-09-27

Inspected revision: `25514f12` on `milestone1`. Investigation only: no product,
collected test, fixture contract, timeout or acceptance rule was changed.
The finite corpus was the five user-named receipts, their retained child logs,
current start/page/bridge/close owners and direct helper consumers, plus the
AB-2 historical helper versions. Historical receipts remain unchanged.

## Disposition

| Incident | Result of this investigation | Remaining uncertainty |
| --- | --- | --- |
| AB-7 Setup | Current installed case passed twice, once unchanged and once with an additional exception observer before adapter normalization. Existing service instrumentation and the new adapter observer captured no start exception. | Original exception/effect phase is unrecoverable from the saved generic `internal_error`; cause remains unknown. |
| AB-7 Plan again | Both window variants passed twice. Current helper captures local before/after click state and waits for settled eligibility. Source confirms pending review work disables the button and fences the handler. | A disabled/early click remains plausible, but the original click had no trace. Current passes cannot prove that explanation or a historical fix. |
| AB-8 stack/wrap | Both variants passed twice; second run used copied helper instrumentation that captures geometry, connection, hidden state and text if the narrow assertion fails. It did not fail. | The old failure saved no geometry. A live render during the helper's animation-frame yield could overwrite its synthetic feedback; this is a source-supported hypothesis only. |
| AB-2 bridge | Original JSON specifically says the child did not exit before the deadline. Historical helper comparison establishes the same sample type mismatch, rejected-promise chain and uncancelable synthetic loop were present. | No original browser report/stacks survived. Same cause is plausible, not established merely from the common exit timeout. |
| AB-10 bridge | Two new installed runs reproduced an early browser failure followed by host-exit deadline. Captured the complete current failure chain below. The old run also retained all four completed 1,500-emission producer files. | Strong compatible mechanism, but the original browser error and close result were not persisted. Do not relabel the exact old run as causally proven. |

## Confirmed current bridge failure chain

1. Product event v5 correctly projects Progress `bytes_done` as a decimal
   string. The optional page copies it directly into sample `position`.
   The helper's `_benchmark_specs.validate_report` permits only an integer or
   null for that field. A direct control using `Envelope`, `Progress` and
   `envelope_to_dict` reproduced `CommandPayloadError: benchmark sample is
   invalid`; changing only position to the equivalent integer was accepted.
2. The installed browser received `BridgeCommandError: The desktop action
   contains invalid data` for the first samples report. The helper chains
   subsequent reports with `reporting.then(...)` on the rejected promise.
   Those callbacks never start or decrement their reserved pending counters.
   Eventually `enqueueReport` throws `benchmark sample reporting is saturated`.
   Run 02 records report_queued=5, report_completed=0 and zero accepted samples.
3. The throw escapes the diagnostic's update callback. Production
   `deliverTaskUpdate` catches it and reports `BridgeTransportError: The desktop
   update could not be applied`. Run 01 captures that outer error; run 02
   observes the original callback exception before rethrowing it unchanged.
4. The page submits a failure report. The helper stores its content in memory,
   writes an empty `benchmark.failure`, and publishes its full milestone only
   after `run_desktop` returns. The empty historical marker was intentional;
   it was not evidence of a failed or truncated JSON write.
5. The parent sends window Close immediately. The synthetic invocation runs
   its fixed 60-second loop without checking cancellation. In run 02, service
   Close returned `complete=false`, four unfinished workers and
   `custody_released=false`. The host therefore kept the window open and
   displayed its normal Retry/Cancel prompt. Run 01's 85-second stack dump
   locates the waiting prompt, not a deadlocked bridge worker.
6. The helper does not answer that prompt or retry Close after producers finish.
   The 110-second parent deadline expires and its owned Job is terminated.
   All four producer files show 1,500 emissions in both fresh runs and AB-10.
   Because host exit never published the full milestone, the original browser
   failure was formerly lost. Copied instrumentation now retains it beforehand.

This is a verified optional diagnostic failure, not evidence that normal sync
work cannot cancel or that production violated shutdown truth. The helper's
string comparison also makes its progress-monotonic diagnostic unreliable
across decimal-width transitions. A complete helper migration must review the
current sample/terminal shapes and shutdown handling; a timeout increase would
not fix the rejected data or reporting chain. No such migration is performed.

## One-off incident boundaries

Setup's normalized exception is after delivery-factory custody. Relevant paths
include request construction, dispatcher admission/attachment, lifecycle receipt
publication and adapter result publication. The existing service observer does
not cover the final adapter publication path; the diagnostic copy additionally
observes `_classify_start_failure` before exception retirement. No occurrence
was induced or replaced with a synthetic refusal. Four active plans in the old
receipt are not evidence of an undocumented four-plan capacity limit.

Plan again's current helper waits for `review.dataset.pending` to clear and for
the button to become enabled. Its current successful observations establish
only present behavior; tracing successful attempts cannot reconstruct the
unobserved original click. No repeat click or increased wait was introduced.

For stack/wrap, the helper writes synthetic status text/visibility, sets 650px
width and yields one animation frame. The live renderer also owns that status
text and its `hidden` flag. The historical receipt lacks the values necessary
to distinguish renderer interference, layout timing, stale elements or another
cause. The new diagnostic captures those values before any reporting roundtrip
on failure. No CSS change or weakened assertion is justified by this pass.

## Runs and retained evidence

- `native-01.log/xml`: 3 passed, 78.12s; unchanged installed Setup and both
  task-shell variants, ordinary test defaults cleared.
- `native-02.log/xml`: 3 passed, 79.99s; same cases with copied test children.
  Product assets remain normal. Diagnostic instrumentation may perturb timing,
  so this is reproduction evidence rather than a replacement acceptance gate.
- `bridge-01.json` and `bridge-02.json`: both incomplete at their unchanged
  110-second scenario deadline, with matching raw-incomplete siblings. These
  contain early browser reports, 85-second thread stacks, producer streams and
  (02) the service-close result. No latency/custody acceptance is claimed.
- `evidence-summary.json`: exact input hashes, source revision, direct sample
  validator red/control pair, hashes of 22 copied native receipts/logs and
  historical/current producer summaries. The bridge driver builds archived HEAD
  product and stages current helper assets; diagnostic differences are in
  `bridge_trace.py`. `native_trace.py` describes all native-helper changes.
- `ab2-page-diff.txt` and `ab2-child-diff.txt`: AB-2 baseline-to-current helper
  comparison. The relevant mismatch/reporting/loop mechanisms are unchanged;
  this establishes prior code presence, not historical execution of every step.

Native fixtures used unique external TEMP roots ending `-01` and `-02`, with
normal desktop access, no pip cache and process-only RemoteSigned. Only test
fixtures were acted on; no real user sync roots were involved. The sample
control initially omitted required `current_path`; its corrected fixture then
produced the recorded red/control result, without modifying production.

## Environment and adversarial review

A bounded Application/System warning/error scan for September 25–27 retained
18 Application and 23 System events, below the 1,000-per-log cap. No matching
Python/WebView crash, display-driver or resource-exhaustion evidence was found.
The selected DWM exit was September 25 03:34:40 local, well before the AB-7
Setup event at September 26 01:23:21 local and AB-8 shell at September 26
18:28 local. This does not prove compositor/process health or exclude a
transient environment cause. Full bounded query/result: `windows_events.ps1`
and `windows-events.json`.

Adversarial checks: historical observations are not upgraded from later passes;
the two bridge incidents are not equated solely by symptom; diagnostic copies
do not certify timing; numeric-control acceptance is not a complete migration;
safe incomplete shutdown is not called a product deadlock; no error was replayed
as a new mutation. All task-owned native processes exited. A separate,
unowned Claude bridge trace was observed afterward and left untouched; its
outputs are not part of this report. No further native run is needed for this
bounded investigation. Unknown causes remain explicitly unknown.

# `build/incident-trace-20260927/native_trace.py`

````python
"""Run existing installed witnesses with diagnostic-only copied children."""
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
WEB = ROOT / "tests/interfaces/web"

def swap(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)

def copy_child(name):
    source = (WEB / name).read_text(encoding="utf-8")
    source = swap(source, "import sys\n", f"import sys\nsys.path.insert(0, {str(WEB)!r})\n")
    return source

setup = copy_child("_setup_headed_child.py")
setup = swap(setup, "    def commands(**kwargs: object) -> object:\n", '''    from namisync.interfaces.web import drain
    original_classify = drain._classify_start_failure
    def classify(error):
        frames = traceback.extract_tb(error.__traceback__)[-12:]
        recorder.observe("pre_normalization_error", {
            "type": type(error).__name__, "message": str(error)[:300],
            "frames": [(Path(f.filename).name, f.lineno, f.name) for f in frames],
        })
        return original_classify(error)
    drain._classify_start_failure = classify

    def commands(**kwargs: object) -> object:
''')
(OUT / "setup_child.py").write_text(setup, encoding="utf-8")

shell = copy_child("_task_shell_headed_child.py")
shell = swap(shell, '  statusCard.style.inlineSize = "650px";', '''  const layoutSnapshot = () => ({
    cardConnected: statusCard.isConnected, detailConnected: statusDetail.isConnected,
    feedbackConnected: feedback.isConnected, feedbackHidden: feedback.hidden,
    feedbackText: feedback.textContent, detailText: statusDetail.textContent,
    cardWidth: statusCard.getBoundingClientRect().width,
    detailWhiteSpace: getComputedStyle(statusDetail).whiteSpace,
    feedbackWhiteSpace: getComputedStyle(feedback).whiteSpace,
    detail: statusDetail.getBoundingClientRect().toJSON(),
    feedback: feedback.getBoundingClientRect().toJSON(),
  });
  const layoutBefore = layoutSnapshot();
  statusCard.style.inlineSize = "650px";''')
shell = swap(shell, '  if (getComputedStyle(statusDetail).whiteSpace !== "normal"', '''  const layoutAfter = layoutSnapshot();
  if (getComputedStyle(statusDetail).whiteSpace !== "normal"''')
shell = swap(shell, '    throw new Error("Narrow status feedback must stack and wrap together");', '''    await control("record", {layout_diagnostic: {before: layoutBefore, after: layoutAfter}});
    throw new Error("Narrow status feedback must stack and wrap together");''')
shell = swap(shell, '  statusCard.style.removeProperty("inline-size");', '''  statusCard.style.removeProperty("inline-size");''')
shell = swap(shell, '            self._data["report"].update(value)', '''            self._data["report"].update(value)
            if "layout_diagnostic" in value:
                Path(__file__).with_name("layout-failure.json").write_text(json.dumps(value), encoding="utf-8")''')
(OUT / "shell_child.py").write_text(shell, encoding="utf-8")

class DiagnosticChildren:
    def pytest_collection_modifyitems(self, items):
        for item in items:
            if item.module.__name__.endswith("test_setup_headed"):
                item.module._CHILD = OUT / "setup_child.py"
            elif item.module.__name__.endswith("test_task_shell_headed"):
                item.module._CHILD = OUT / "shell_child.py"

run = sys.argv[1]
raise SystemExit(pytest.main([
    "-q", "-o", "addopts=",
    "tests/interfaces/web/test_setup_headed.py::test_m1_6_installed_setup_flow",
    "tests/interfaces/web/test_task_shell_headed.py::test_m1_4_installed_task_shell_navigation_closure_and_recovery",
    "--basetemp", f"C:/Users/Spectrum/AppData/Local/Temp/NamiSync-incident-20260927-{run}",
    "--junitxml", str(OUT / f"native-{run}.xml"),
], plugins=[DiagnosticChildren()]))
````

# `build/trace-20260927/scripts/plan-again/map_base_lines_9_490.py`

````python
import subprocess, sys
data = subprocess.check_output(["git", "show", "2b4a2214:tests/interfaces/web/_task_shell_headed_child.py"]).decode("utf-8")
lines = data.splitlines()
end = next(i + 1 for i in range(80, 330) if lines[i].startswith('"""'))
start = next(i + 1 for i, line in enumerate(lines) if line.startswith("_PLAN_REVIEW_SCRIPT = "))
common_js_lines = end - 81  # JS lines contributed by _COMMON_JS (0-based count)
print("common closes", end, "plan starts", start)
# JS text = _COMMON_JS + plan; 0-based JS line n. _COMMON_JS text begins after r""" on line 81.
js = (("\n".join(lines[80:end]))[len('_COMMON_JS = r"""'):]).rsplit('"""', 1)[0]
plan_body = "\n".join(lines[start-1:]).split('r"""', 1)[1].split('\n"""', 1)[0]
full = js + plan_body
jl = full.split("\n")
for n in (9, 490):
    print(f"JS0 {n}: {jl[n].strip()}")
    for k in range(n - 5, n + 2):
        print(f"   {k}: {jl[k]}")
````

# `build/trace-20260927/scripts/plan-again/map_line_411_variants.py`

````python
import subprocess
data = subprocess.check_output(["git", "show", "6287db0c:tests/interfaces/web/_task_shell_headed_child.py"]).decode("utf-8")
settled = '''  await until(() => viewport.textContent.includes("insufficient_space")
    && review.dataset.pending === ""
    && review.querySelector('[data-action="plan-again"]')?.disabled === false,
  "settled review refusal notice");'''
original = '''  await until(() => viewport.textContent.includes("insufficient_space"), "review refusal notice");'''
assert settled in data
variants = {"6287db0c": data, "6287db0c-minus-settle-wait": data.replace(settled, original)}
for name, text in variants.items():
    lines = text.splitlines()
    end = next(i + 1 for i in range(80, 330) if lines[i].startswith('"""'))
    start = next(i + 1 for i, line in enumerate(lines) if line.startswith("_PLAN_REVIEW_SCRIPT = "))
    js = (("\n".join(lines[80:end]))[len('_COMMON_JS = r"""'):]).rsplit('"""', 1)[0]
    plan_body = "\n".join(lines[start-1:]).split('r"""', 1)[1].split('\n"""', 1)[0]
    jl = (js + plan_body).split("\n")
    print("==", name)
    for k in range(407, 414):
        print(("=> " if k == 411 else "   ") + f"{k}: {jl[k]}")
````

# `build/trace-20260927/scripts/plan-again/notice_position.py`

````python
"""Where does the forced review-refusal notice sit in the canonical Plan view?

Rebuilds the task-shell headed fixture (shared.txt, 300 z-files, nested folder,
forced INSUFFICIENT_SPACE preflight refusal) against the real service and
reports the notice row's visible index in the unfiltered and notice-filtered
windows.
"""

from __future__ import annotations

import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path.cwd()))

from namisync.core.preflight import Refusal, RefusalCode, Verdict  # noqa: E402
from namisync.interfaces.service import NamiSyncService  # noqa: E402
from namisync.interfaces.web import drain as drain_mod  # noqa: E402
from namisync.interfaces.web.bridge import (  # noqa: E402
    BridgeResponseTooLargeError,
    _admit_task_drain_response_prefix,
    _consume_task_drain_response,
    _peek_task_drain_response,
)
from namisync.interfaces.web.paths import AppPaths  # noqa: E402
from namisync.workflows import LocationCandidate, LocationCandidateKind  # noqa: E402

base = Path(sys.argv[1]).resolve()
source, target = base / "source", base / "target"
source.mkdir(parents=True)
target.mkdir()
(source / "shared.txt").write_text("source-v1", encoding="utf-8")
(target / "shared.txt").write_text("target-before-v1", encoding="utf-8")
for index in range(300):
    (source / f"z-{index:03d}.txt").write_text("fixture", encoding="utf-8")
nested = source / "nested-folder" / "child-folder"
nested.mkdir(parents=True)
(nested / "child.txt").write_text("nested fixture", encoding="utf-8")

paths = AppPaths.from_root(base / "data")
paths.ensure_directories()
service = NamiSyncService(paths.ledger, paths.history, settings_path=paths.settings)
registry = drain_mod.TaskRegistry(service)
registry.bind_response_codec(drain_mod._TaskDrainResponseCodec(
    BridgeResponseTooLargeError, _admit_task_drain_response_prefix,
    _peek_task_drain_response, _consume_task_drain_response,
))
deps = service._runtime._deps
service._runtime._deps = replace(
    deps,
    preflight=lambda review, world, **kwargs: Verdict(
        False,
        (Refusal(RefusalCode.INSUFFICIENT_SPACE, detail="headed review refusal"),),
        world,
    ),
)


def literal(path: Path) -> LocationCandidate:
    return LocationCandidate(LocationCandidateKind.LITERAL_PATH, path=str(path))


try:
    options = registry.prepare_setup_options(registry.read_setup_options())
    shell = registry.create_task_shell(uuid4().hex)
    command = uuid4().hex
    start = registry.start_setup_plan(
        shell.task_id, literal(source), literal(target), options,
        command_id=command, wire_intent=("start-plan", shell.task_id, command),
    )
    while True:
        view = registry.drain(start.task_id, start.session_id, uuid4().hex, replay_from=None)
        if any(type(u).__name__ == "TaskRecordUpdateView" for u in view.updates):
            break
    registry.release_terminal_session(start.task_id, start.session_id)
    for _ in range(100):
        try:
            summary = registry.open_plan_view(start.task_id)
            break
        except Exception:
            time.sleep(0.05)
    print("summary keys:", sorted(summary))
    print("visible_row_count", summary.get("visible_row_count"),
          "sort", summary.get("sort_column"), summary.get("sort_direction"),
          "filters", summary.get("filters"), "refusals", summary.get("preflight_refusal_count"))
    window = registry.get_plan_window(
        start.task_id, expected_revision=summary["view_revision"], offset=0, limit=256,
    )
    rows = window["rows"]
    print("window total", window["total"], "rows", len(rows))
    for row in rows[:6]:
        print("  first:", row["visible_index"], row.get("row_kind"), repr(row.get("display"))[:70],
              "notice=", repr(row.get("notice"))[:60])
    hits = [row for row in rows if "insufficient_space" in str(row.get("notice")) + str(row.get("display"))]
    print("notice rows in first 256:", [(row["visible_index"], row.get("display")) for row in hits])
finally:
    registry.begin_close()
    service.close()
    shutil.rmtree(base, ignore_errors=True)
````

# `build/trace-20260927/scripts/plan-again/order_base_checkpoints.py`

````python
import subprocess
data = subprocess.check_output(["git", "show", "2b4a2214:tests/interfaces/web/_task_shell_headed_child.py"]).decode("utf-8")
lines = data.splitlines()
end = next(i + 1 for i in range(80, 330) if lines[i].startswith('"""'))
start = next(i + 1 for i, line in enumerate(lines) if line.startswith("_PLAN_REVIEW_SCRIPT = "))
js = (("\n".join(lines[80:end]))[len('_COMMON_JS = r"""'):]).rsplit('"""', 1)[0]
plan_body = "\n".join(lines[start-1:]).split('r"""', 1)[1].split('\n"""', 1)[0]
jl = (js + plan_body).split("\n")
for k, text in enumerate(jl):
    if any(s in text for s in ('fresh Plan-again', '"plan_again"', '"plan_force"', 'planAgain', 'plan-again"]\').click', "Plan-again selection", "changed source plan row")):
        print(k, text.strip()[:150])
````
