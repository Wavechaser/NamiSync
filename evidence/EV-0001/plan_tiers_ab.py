"""Read-only planner for build\\ cleanup Tiers A and B. Writes tierab-manifest.csv and tierab-plan.json.

Tier A: whole top-level entries cited by no active tracked file (uncited or docs/obsolete only).
Tier B: regenerable populations inside actively cited roots:
  venv     - venv files except pyvenv.cfg and *.dist-info (version record kept)
  runtime  - standalone Python installs no retained venv uses as home
  pytest   - pytest temp files except receipt/capture extensions
  frozen   - frozen-app trees whose every file matches a retained ZIP member (path, size, CRC32)
  sqlite   - SQLite databases and sidecars (opt-in line; listed separately)
Holds win over every rule. Nothing is deleted here.
"""
import csv, json, os, stat, subprocess, sys, zipfile, zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
REPO = BUILD.parent
RECEIPT_EXT = {".json", ".jsonl", ".png", ".log", ".xml", ".txt", ".html", ".md", ".csv", ".bmp", ".dmp", ".patch", ".diff",
               ".zip", ".whl", ".bundle"}
SQLITE_EXT = {".db", ".db-wal", ".db-shm", ".db-journal", ".sqlite"}
HOLD_DIRS = [  # relative to build, lowercase compare
    HERE.name,
    "gui-tuning",
    r"m1-r5-20261111\checkout",
    r"m1-release-repair-20261110\acceptance-checkout",
    r"m1-release-repair-20261110\idle-followup-checkout",
    r"m1-r5-20261111\delivery",
    r"m1-r5-20261111\delivery-package04-draft",
]
HOLD_PREFIX_FILES = ("build_cleanup_",)


def rel(p: Path) -> str:
    return str(p.relative_to(BUILD))


def is_reparse(p: Path) -> bool:
    return bool(os.lstat(p).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def held(r: str) -> bool:
    low = r.lower()
    if Path(r).parts[0].lower().startswith(HOLD_PREFIX_FILES):
        return True
    return any(low == h.lower() or low.startswith(h.lower() + "\\") for h in HOLD_DIRS)


def walk(top: Path):
    """Yield (path, is_reparse) for files and reparse points under top, never following reparse points."""
    stack = [top]
    while stack:
        d = stack.pop()
        with os.scandir(d) as it:
            for e in it:
                p = Path(e.path)
                if is_reparse(p):
                    yield p, True
                elif e.is_dir(follow_symlinks=False):
                    stack.append(p)
                else:
                    yield p, False


def cited_files() -> set[str]:
    out = subprocess.run(["git", "grep", "-I", "-h", "-o", "-E", r"build[/\\][^ `)\"'<>|*]+", "--", ".", ":!build"],
                         cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout
    return {line.strip().rstrip(".,;:").replace("/", "\\").split("\\", 1)[1].lower() for line in out.splitlines() if "\\" in line.replace("/", "\\")}


rows: list[dict] = []
counted: set[str] = set()


def add(p: Path, tier: str, rule: str, proof: str, link: bool = False):
    r = rel(p)
    if r in counted or held(r) or r.lower() in CITED:
        return
    st = os.lstat(p)
    counted.add(r)
    rows.append({"tier": tier, "rule": rule, "path": r, "kind": "link" if link else "file",
                 "size": 0 if link else st.st_size, "mtime_ns": st.st_mtime_ns, "proof": proof})


def link_proof(p: Path) -> str | None:
    try:
        target = os.readlink(p)
    except OSError:
        return None
    t = target.removeprefix("\\\\?\\")
    return f"junction->{t}" if t.lower().startswith(str(BUILD).lower() + "\\") else None


CITED = cited_files()
classes = {r["name"]: r["class"] for r in csv.DictReader(open(HERE / "build-citations.csv", encoding="utf-8-sig"))}
anchors = list(csv.DictReader(open(HERE / "tierb-anchors.csv", encoding="utf-8-sig")))
skipped: list[dict] = []

# Tier A
receipt_cited = set((HERE / "tiera-receipt-cited.txt").read_text(encoding="utf-8-sig").split())
for name, cls in sorted(classes.items()):
    if cls == "active" or held(name):
        continue
    if cls == "uncited" and name in receipt_cited:
        skipped.append({"path": name, "reason": "uncited but named by a retained evidence receipt"})
        continue
    p = BUILD / name
    if p.is_file():
        add(p, "A", cls, "no active tracked citation")
        continue
    for f, link in walk(p):
        if link:
            proof = link_proof(f)
            if proof:
                add(f, "A", cls, proof, link=True)
            else:
                skipped.append({"path": rel(f), "reason": "reparse target outside build"})
        else:
            add(f, "A", cls, "no active tracked citation")

# Tier B anchors (only inside active roots; Tier A roots already covered whole)
def active(r: str) -> bool:
    return classes.get(Path(r).parts[0]) == "active"

venv_homes = set()
for cfg in BUILD.rglob("pyvenv.cfg"):
    vr = rel(cfg.parent)
    if held(vr) or not any(a["kind"] == "venv" and a["path"] == vr and active(vr) for a in anchors):
        # retained venv: keep its interpreter
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.split("=")[0].strip() == "home":
                venv_homes.add(line.split("=", 1)[1].strip().lower())

for a in anchors:
    r = a["path"]
    if not active(r) or held(r):
        continue
    root = BUILD / r
    if a["kind"] == "venv":
        for f, link in walk(root):
            fr = rel(f).lower()
            if link or f.name == "pyvenv.cfg" or ".dist-info\\" in fr:
                continue
            add(f, "B", "venv", "installed environment; dist-info and pyvenv.cfg kept")
    elif a["kind"] == "python-install":
        if str(root).lower() in venv_homes:
            skipped.append({"path": r, "reason": "home of a retained venv"})
            continue
        for f, link in walk(root):
            if not link:
                add(f, "B", "runtime", "standalone interpreter; no retained venv uses it")
    elif a["kind"] == "pytest-root":
        for f, link in walk(root):
            if link:
                proof = link_proof(f)
                if proof:
                    add(f, "B", "pytest", proof, link=True)
                continue
            if f.suffix.lower() not in RECEIPT_EXT:
                add(f, "B", "pytest", "pytest temp state; receipts/captures kept")
    elif a["kind"] == "frozen-app":
        files = [f for f, link in walk(root) if not link]
        top = BUILD / Path(r).parts[0]
        zips = [z for z, link in walk(top) if not link and z.suffix.lower() == ".zip" and not held(rel(z))]
        match = None
        for z in zips:
            try:
                with zipfile.ZipFile(z) as zf:
                    info = {i.filename.replace("/", "\\").lower(): i for i in zf.infolist() if not i.is_dir()}
            except zipfile.BadZipFile:
                continue
            for prefix in ("", root.name.lower() + "\\"):
                ok = True
                for f in files:
                    i = info.get(prefix + str(f.relative_to(root)).lower())
                    if i is None or i.file_size != f.stat().st_size:
                        ok = False
                        break
                if ok and files:
                    ok = all(zlib.crc32(f.read_bytes()) == info[prefix + str(f.relative_to(root)).lower()].CRC for f in files)
                if ok and files:
                    match = rel(z)
                    break
            if match:
                break
        if not match:
            skipped.append({"path": r, "reason": "no retained ZIP matches every file"})
            continue
        for f in files:
            add(f, "B", "frozen", f"matches {match} (path,size,CRC32)")

# Tier B sqlite (opt-in), active roots only, outside holds
for name, cls in classes.items():
    p = BUILD / name
    if cls != "active" or held(name) or not p.is_dir():
        continue
    for f, link in walk(p):
        if not link and f.suffix.lower() in SQLITE_EXT:
            add(f, "B", "sqlite", "SQLite state; regenerable by rerun (opt-in)")

with open(HERE / "tierab-manifest.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["tier", "rule", "path", "kind", "size", "mtime_ns", "proof"])
    w.writeheader()
    w.writerows(rows)

summary: dict = {}
for row in rows:
    k = f'{row["tier"]}:{row["rule"]}'
    s = summary.setdefault(k, {"entries": 0, "bytes": 0})
    s["entries"] += 1
    s["bytes"] += row["size"]
plan = {"head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
        "holds": HOLD_DIRS + ["build_cleanup_* files", "exactly cited file paths"],
        "summary": summary, "skipped": skipped,
        "total": {"entries": len(rows), "bytes": sum(r["size"] for r in rows)}}
(HERE / "tierab-plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
for k, v in sorted(summary.items()):
    print(f"{k:18} {v['entries']:8,} {v['bytes'] / 2**20:10,.1f} MiB")
print(f"{'total':18} {len(rows):8,} {plan['total']['bytes'] / 2**20:10,.1f} MiB")
for s in skipped:
    print("skip:", s["path"], "-", s["reason"])
