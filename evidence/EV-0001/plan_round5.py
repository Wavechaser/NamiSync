"""Read-only planner for round 5. Turns round5-candidates.csv into round5-manifest.csv (executor format).

Rules: pyi-work, frozen2, git-copy (see measure_round5.py for proofs). Adds the holds measure_round5 lacked:
exactly cited file paths. Drops frozen2 rows whose proof ZIP is itself a candidate, and pyi-work rows that are
not under a PyInstaller work directory (one holding a .pkg or PYZ-*.pyz directly).
"""
import csv, os, stat, subprocess
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
REPO = BUILD.parent

out = subprocess.run(["git", "grep", "-I", "-h", "-o", "-E", r"build[/\\][^ `)\"'<>|*]+", "--", ".", ":!build"],
                     cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout
CITED = {l.strip().rstrip(".,;:").replace("/", "\\").split("\\", 1)[1].lower() for l in out.splitlines() if "\\" in l.replace("/", "\\")}

cands = [r for r in csv.DictReader(open(HERE / "round5-candidates.csv", encoding="utf-8")) if r["rule"] in ("pyi-work", "frozen2", "git-copy")]
cand_paths = {r["path"].lower() for r in cands}
rows, dropped = [], Counter()
for r in cands:
    p = BUILD / r["path"]
    low = r["path"].lower()
    if low in CITED or any(low.startswith(c + "\\") for c in ()):
        dropped["cited"] += 1; continue
    if r["rule"] == "frozen2" and r["proof"].lower() in cand_paths:
        dropped["proof-zip-is-candidate"] += 1; continue
    if r["rule"] == "pyi-work":
        d = p.parent
        while d != BUILD and not (any(d.glob("*.pkg")) or any(d.glob("PYZ-*.pyz"))):
            d = d.parent
        if d == BUILD:
            dropped["pyi-not-in-workdir"] += 1; continue
    try:
        st = os.lstat(p)
    except FileNotFoundError:
        dropped["absent"] += 1; continue
    if st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        dropped["reparse"] += 1; continue
    rows.append({"tier": "5", "rule": r["rule"], "path": r["path"], "kind": "file", "size": st.st_size,
                 "mtime_ns": st.st_mtime_ns, "proof": r["proof"] or "git blob reachable" if r["rule"] == "git-copy" else r["proof"] or "pyinstaller work intermediate"})
with open(HERE / "round5-manifest.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["tier", "rule", "path", "kind", "size", "mtime_ns", "proof"]); w.writeheader(); w.writerows(rows)
tot = Counter(); n = Counter()
for r in rows:
    tot[r["rule"]] += r["size"]; n[r["rule"]] += 1
for k in sorted(n):
    print(f"{k:10} {n[k]:7,} {tot[k] / 2**20:8,.1f} MiB")
print("dropped", dict(dropped))
print("pyi-work dirs:", sorted({str(Path(r['path']).parent) for r in rows if r['rule'] == 'pyi-work'})[:40])
