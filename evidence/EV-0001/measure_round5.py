"""Read-only: size candidate populations for a further build reduction. Writes round5-candidates.csv.

git-copy  : non-receipt text/source files whose Git blob id is reachable from refs (restorable by blob id)
pyi-work  : PyInstaller work-dir intermediates (.pkg .pyz .exe .dll .pyd .zip) beside retained outputs
frozen2   : app trees not yet removed whose every file matches some retained ZIP anywhere in build
"""
import csv, hashlib, os, stat, subprocess, zipfile, zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
REPO = BUILD.parent
HOLD = [HERE.name.lower(), "gui-tuning", r"m1-r5-20261111\checkout", r"m1-release-repair-20261110\acceptance-checkout",
        r"m1-release-repair-20261110\idle-followup-checkout", r"m1-r5-20261111\delivery", r"m1-r5-20261111\delivery-package04-draft"]
GIT_EXT = {".py", ".js", ".css", ".html", ".md", ".txt", ".toml", ".svg", ".ps1", ".json", ".ini", ".cfg", ".yml", ".typed", ""}


def held(r: str) -> bool:
    low = r.lower()
    return low.split("\\")[0].startswith("build_cleanup_") or any(low == h or low.startswith(h + "\\") for h in HOLD)


def files():
    stack = [BUILD]
    while stack:
        d = stack.pop()
        with os.scandir(d) as it:
            for e in it:
                if e.is_symlink() or (e.stat(follow_symlinks=False).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                    continue
                if e.is_dir(follow_symlinks=False):
                    stack.append(Path(e.path))
                else:
                    yield Path(e.path)


all_files = [f for f in files() if not held(str(f.relative_to(BUILD)))]
rows = []

# git-copy
reachable = set()
out = subprocess.run(["git", "rev-list", "--objects", "--all"], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
for line in out.splitlines():
    reachable.add(line[:40])
cands = [f for f in all_files if f.suffix.lower() in GIT_EXT]
unreadable = 0
for f in cands:
    try:
        data = f.read_bytes()
    except OSError:
        unreadable += 1
        continue
    h = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    if h in reachable:
        rows.append(("git-copy", f, len(data), h))
print("unreadable candidates:", unreadable)

# zip index across build
zips = {}
for z in all_files:
    if z.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(z) as zf:
                zips[z] = {i.filename.replace("/", "\\").lower(): i for i in zf.infolist() if not i.is_dir()}
        except (zipfile.BadZipFile, OSError):
            pass

# pyi-work: dirs holding a *.pkg or PYZ-*.pyz
for d in {f.parent for f in all_files if f.suffix.lower() in (".pkg", ".pyz")}:
    for f in d.rglob("*"):
        if f.is_file() and f.suffix.lower() in (".pkg", ".pyz", ".exe", ".dll", ".pyd", ".zip") and not held(str(f.relative_to(BUILD))):
            rows.append(("pyi-work", f, f.stat().st_size, ""))

# frozen2: remaining app trees (dir with _internal + an exe)
for d in {f.parent for f in all_files if f.parent.name != "_internal" and (f.parent / "_internal").is_dir() and f.suffix.lower() == ".exe"}:
    tree = [f for f in d.rglob("*") if f.is_file()]
    for z, info in zips.items():
        if d in z.parents:
            continue
        for prefix in ("", d.name.lower() + "\\"):
            if all((i := info.get(prefix + str(f.relative_to(d)).lower())) and i.file_size == f.stat().st_size for f in tree) and \
               all(zlib.crc32(f.read_bytes()) == info[prefix + str(f.relative_to(d)).lower()].CRC for f in tree):
                rows += [("frozen2", f, f.stat().st_size, str(z.relative_to(BUILD))) for f in tree]
                break
        else:
            continue
        break
    else:
        rows.append(("frozen2-unmatched", d, 0, ""))

seen, uniq = set(), []
for r in rows:
    if r[1] not in seen:
        seen.add(r[1]); uniq.append(r)
with open(HERE / "round5-candidates.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["rule", "path", "size", "proof"])
    for rule, p, s, proof in uniq:
        w.writerow([rule, str(p.relative_to(BUILD)), s, proof])
tot = {}
for rule, p, s, _ in uniq:
    t = tot.setdefault(rule, [0, 0]); t[0] += 1; t[1] += s
for k, (n, b) in sorted(tot.items()):
    print(f"{k:18} {n:8,} {b / 2**20:9,.1f} MiB")
print("remaining files considered:", len(all_files))
