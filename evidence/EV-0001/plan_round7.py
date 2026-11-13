"""Round 7 (2026-11-14): apply the ratified retention policy. Reads policy-files.csv (rerun measure_policy.py first).

Keep:
  lasting   : cited by an active lasting doc. Exception rule hdr-capture: gui-tuning .bmp/.rgbaf16 captures.
  m1plan    : cited only by M1_PLAN (early-M2 reference): keep text records outside workspace trees.
  survey    : this folder (session working ledger; promoted/cleaned at closeout).
Delete:
  hdr-capture      : gui-tuning full-resolution HDR/WCG captures (user: recreatable while DWM is unfixed).
  r5-package       : m1-r5-20261111 delivery / draft / github-release trees (tester set stays in dist/v0.1.0).
  m1plan-workspace : under M1_PLAN-only coverage, non-record files and anything inside a workspace tree
                     (Git checkout, Python runtime/venv, PyInstaller work, temp trees).
  unretained       : cited only by CHANGELOG (wcg-review, user: remakeable), HANDOFF, obsolete docs, code, or uncited.
Files modified after FRESH are held (possible live work of another session). Writes round7-manifest.csv, round7-plan.json.
"""
import csv, json, os, stat
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
FRESH_NS = int(datetime.fromisoformat("2026-11-13T00:00:00+08:00").timestamp()) * 10**9  # later mtimes are held
RECORD = {".json", ".jsonl", ".csv", ".md", ".txt", ".log", ".xml", ".html", ".patch", ".diff", ".tsv", ".err", ".out"}
R5_PACKAGES = ("m1-r5-20261111\\delivery\\", "m1-r5-20261111\\delivery-package04-draft\\", "m1-r5-20261111\\github-release\\")
TEMP_WORDS = ("tmp", "temp")


def workspace_roots() -> set[str]:
    """Directories (lowercase rel) that are workspace trees by content marker or temp naming."""
    roots = set()
    stack = [BUILD]
    while stack:
        d = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        names = {e.name.lower() for e in entries}
        rel = str(d.relative_to(BUILD)).lower()
        leaf = d.name.lower()
        if d != BUILD and (".git" in names or "pyvenv.cfg" in names or "python.exe" in names or leaf == "site-packages"
                           or any(n.endswith(".toc") for n in names) or any(w in leaf for w in TEMP_WORDS)):
            roots.add(rel)
            continue
        for e in entries:
            if e.is_dir(follow_symlinks=False) and not (e.stat(follow_symlinks=False).st_file_attributes
                                                       & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                stack.append(Path(e.path))
    return roots


def main() -> None:
    ws = workspace_roots()
    rows, held, kept = [], Counter(), Counter()
    for r in csv.DictReader(open(HERE / "policy-files.csv", encoding="utf-8")):
        rel, cov = r["path"], r["coverage"]
        if rel.startswith("mop-up-survey-20261111\\"):
            kept["survey"] += 1
            continue
        p = BUILD / rel
        try:
            st = os.lstat(p)
        except FileNotFoundError:
            continue
        if st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            held["reparse"] += 1
            continue
        if st.st_mtime_ns >= FRESH_NS:
            held["fresh"] += 1
            print("fresh hold:", rel)
            continue
        parts = rel.split("\\")
        in_ws = any("\\".join(parts[:i]) in ws for i in range(1, len(parts)))
        rule = None
        if cov == "lasting":
            if rel.startswith("gui-tuning\\") and Path(rel).suffix in (".bmp", ".rgbaf16"):
                rule = "hdr-capture"
        elif rel.startswith(R5_PACKAGES):
            rule = "r5-package"
        elif cov == "m1plan":
            if Path(rel).suffix not in RECORD or in_ws:
                rule = "m1plan-workspace"
        else:
            rule = "unretained"
        if rule is None:
            kept[cov] += 1
            continue
        rows.append({"tier": "r7", "rule": rule, "path": rel, "kind": "file", "size": st.st_size,
                     "mtime_ns": st.st_mtime_ns, "proof": cov})
    with open(HERE / "round7-manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["tier", "rule", "path", "kind", "size", "mtime_ns", "proof"])
        w.writeheader(); w.writerows(rows)
    by = Counter(); size = Counter()
    for x in rows:
        by[x["rule"]] += 1; size[x["rule"]] += x["size"]
    plan = {"rules": {k: {"files": by[k], "bytes": size[k]} for k in sorted(by)}, "kept_files": dict(kept),
            "held": dict(held), "workspace_roots": len(ws)}
    (HERE / "round7-plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
