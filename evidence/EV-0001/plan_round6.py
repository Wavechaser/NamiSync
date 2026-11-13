"""Read-only planner for round 6: leftover test files in closed roots. Writes round6-manifest.csv.

Closed roots = top-level dirs except release roots, gui-tuning and this survey folder (same set as
measure_closed_classes.py). Rules:
  pytest-left  : files under a pytest basetemp (a dir holding test_<name<=30>N children, or pytest-of-*)
                 whose extension is not a receipt/capture extension; rebuilt .whl files are included
  synth-data   : outside pytest temp, synthetic payload files (.bin .original .restored)
Holds: exactly cited file paths, build_cleanup_*, reparse points (never followed).
"""
import csv, json, os, re, stat, subprocess
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
REPO = BUILD.parent
KEEP_LIVE = {HERE.name, "gui-tuning", "m1-r5-20261111", "m1-release-repair-20261110", "m1-r4-20261109",
             "m1-release-20261104", "m1-r2-20261109"}
KEEP_EXT = {".json", ".jsonl", ".png", ".log", ".xml", ".txt", ".html", ".md", ".csv", ".bmp", ".dmp", ".patch", ".diff",
            ".zip", ".bundle", ".heapsnapshot", ".tsv", ".err", ".out", ".jpg", ".jpeg", ".gif", ".webm", ".mp4", ".har", ".etl"}
SYNTH_EXT = {".bin", ".original", ".restored"}
TESTDIR = re.compile(r"^test_.{1,30}\d+$")

out = subprocess.run(["git", "grep", "-I", "-h", "-o", "-E", r"build[/\\][^ `)\"'<>|*]+", "--", ".", ":!build"],
                     cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout
CITED = {l.strip().rstrip(".,;:").replace("/", "\\").split("\\", 1)[1].lower() for l in out.splitlines() if "\\" in l.replace("/", "\\")}


def reparse(p) -> bool:
    return bool(os.lstat(p).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


rows, held, ext = [], Counter(), Counter()
for top in sorted(p for p in BUILD.iterdir() if p.is_dir() and p.name not in KEEP_LIVE and not reparse(p)):
    def walk(d: Path, base: Path | None):
        ents = list(os.scandir(d))
        dirs = [e for e in ents if e.is_dir(follow_symlinks=False) and not reparse(e.path)]
        if base is None and (d.name.startswith("pytest-of-") or any(TESTDIR.match(e.name) for e in dirs)):
            base = d
        for e in ents:
            if not e.is_file(follow_symlinks=False) or reparse(e.path):
                continue
            p = Path(e.path); x = p.suffix.lower(); r = str(p.relative_to(BUILD))
            if base is not None and x not in KEEP_EXT:
                rule, proof = "pytest-left", "basetemp " + str(base.relative_to(BUILD))
            elif base is None and x in SYNTH_EXT:
                rule, proof = "synth-data", "synthetic payload"
            else:
                continue
            if r.lower() in CITED:
                held["cited"] += 1; continue
            st = os.lstat(p)
            rows.append({"tier": "6", "rule": rule, "path": r, "kind": "file", "size": st.st_size,
                         "mtime_ns": st.st_mtime_ns, "proof": proof})
            ext[(rule, x or "(none)")] += st.st_size
        for e in dirs:
            walk(Path(e.path), base)
    walk(top, None)

with open(HERE / "round6-manifest.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["tier", "rule", "path", "kind", "size", "mtime_ns", "proof"]); w.writeheader(); w.writerows(rows)
summary = {}
for r in rows:
    s = summary.setdefault(r["rule"], {"files": 0, "bytes": 0}); s["files"] += 1; s["bytes"] += r["size"]
bases = Counter(r["proof"] for r in rows if r["rule"] == "pytest-left")
(HERE / "round6-plan.json").write_text(json.dumps({"summary": summary, "held": held, "basetemps": len(bases),
                                                    "keep_ext": sorted(KEEP_EXT)}, indent=2), encoding="utf-8")
print(json.dumps(summary), "held", dict(held), "basetemps", len(bases))
for (rule, x), b in ext.most_common(25):
    print(f"  {rule:12} {x:12} {b / 2**20:8.1f} MiB")
