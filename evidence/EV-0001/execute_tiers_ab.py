"""Execute tierab-manifest.csv. Usage: python -I execute_tiers_ab.py RULE [RULE ...] | --verify RULE [...]

RULEs: obsolete-only uncited venv runtime pytest frozen sqlite (tierab-manifest.csv);
pyi-work frozen2 git-copy (round5-manifest.csv); pytest-left synth-data (round6-manifest.csv);
hdr-capture r5-package m1plan-workspace unretained (round7-manifest.csv). Each row is re-checked immediately before
removal: path inside build, not under a hold, unchanged size and mtime, and file rows must not be reparse
points; link rows must still be junctions/symlinks targeting build and are removed as links only (never
followed). Directories are removed afterwards only by non-recursive rmdir when empty, deepest first.
Journal: tierab-journal.jsonl (append). Denied/changed rows are recorded and left in place.
"""
import csv, json, os, stat, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
JOURNAL = HERE / "tierab-journal.jsonl"
RULES = {"obsolete-only", "uncited", "venv", "runtime", "pytest", "frozen", "sqlite", "pyi-work", "frozen2", "git-copy",
         "pytest-left", "synth-data", "hdr-capture", "r5-package", "m1plan-workspace", "unretained"}


def reparse(p: Path) -> bool:
    return bool(os.lstat(p).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def inside_build(p: Path) -> bool:
    try:
        Path(os.path.abspath(p)).relative_to(BUILD)
        return True
    except ValueError:
        return False


def main(argv: list[str]) -> int:
    verify = argv[:1] == ["--verify"]
    rules = set(argv[1:] if verify else argv)
    if not rules or not rules <= RULES:
        print(__doc__)
        return 2
    rows = [r for m in ("tierab-manifest.csv", "round5-manifest.csv", "round6-manifest.csv", "round7-manifest.csv")
            for r in csv.DictReader(open(HERE / m, encoding="utf-8")) if r["rule"] in rules]
    if verify:
        present = [r["path"] for r in rows if os.path.lexists(BUILD / r["path"])]
        print(json.dumps({"rules": sorted(rules), "planned": len(rows), "still_present": len(present), "sample": present[:20]}))
        return 0 if not present else 1
    counts = {"removed": 0, "bytes": 0, "absent": 0, "changed": 0, "denied": 0}
    parents: set[Path] = set()
    with open(JOURNAL, "a", encoding="utf-8") as j:
        for r in rows:
            p = BUILD / r["path"]
            rec = {"t": time.time(), "rule": r["rule"], "path": r["path"]}
            if not inside_build(p) or p.parent == HERE or HERE in p.parents:
                rec["result"] = "guard"
                counts["changed"] += 1
            elif not os.path.lexists(p):
                rec["result"] = "absent"
                counts["absent"] += 1
            else:
                st = os.lstat(p)
                is_link = reparse(p)
                ok = (is_link and r["kind"] == "link" and inside_build(Path(os.readlink(p).removeprefix("\\\\?\\")))) or \
                     (not is_link and r["kind"] == "file" and st.st_size == int(r["size"]) and st.st_mtime_ns == int(r["mtime_ns"]))
                if not ok:
                    rec["result"] = "changed"
                    counts["changed"] += 1
                else:
                    try:
                        if is_link:
                            os.rmdir(p)  # removes a directory junction/symlink itself, not its target
                        else:
                            if st.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY:
                                os.chmod(p, stat.S_IWRITE)
                            os.unlink(p)
                        rec["result"] = "removed"
                        counts["removed"] += 1
                        counts["bytes"] += 0 if is_link else st.st_size
                        parents.add(p.parent)
                    except PermissionError as e:
                        rec["result"] = f"denied: {e.winerror}"
                        counts["denied"] += 1
            j.write(json.dumps(rec) + "\n")
    removed_dirs = 0
    for d in sorted({a for p in parents for a in [p, *p.parents] if inside_build(a) and a != BUILD},
                    key=lambda x: len(x.parts), reverse=True):
        try:
            if d.exists() and not reparse(d) and not any(d.iterdir()):
                d.rmdir()
                removed_dirs += 1
        except OSError:
            pass
    counts["removed_dirs"] = removed_dirs
    print(json.dumps({"rules": sorted(rules), "planned": len(rows), **counts}))
    return 0 if not counts["changed"] and not counts["denied"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
