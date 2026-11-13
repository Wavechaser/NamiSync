"""Read-only: build\\ coverage under the ratified retention policy (2026-11-14). Writes policy-cited.csv, policy-files.csv.

Citer classes: lasting (active .md docs other than below), m1plan (docs/M1_PLAN.md), changelog, handoff,
obsolete (docs/obsolete/**), code (other tracked files). Coverage of a file = strongest class among its citers in
that order. Prints per cited path (lasting / m1plan) its existing bytes and per root totals.
"""
import csv, os, stat, subprocess
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
REPO = BUILD.parent
ORDER = ("lasting", "m1plan", "changelog", "handoff", "obsolete", "code", "uncited")


def citer_class(f: str) -> str:
    f = f.replace("\\", "/")
    if f == "docs/M1_PLAN.md":
        return "m1plan"
    if f == "CHANGELOG.md":
        return "changelog"
    if f == "docs/HANDOFF.md":
        return "handoff"
    if f.startswith("docs/obsolete/"):
        return "obsolete"
    return "lasting" if f.endswith(".md") else "code"


out = subprocess.run(["git", "grep", "-n", "-I", "-o", "-E", r"build[/\\][^ `)\"'<>|*]+", "--", ".", ":!build"],
                     cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout
cites = defaultdict(set)  # cited rel path (lower) -> {"file:line"}
for line in out.splitlines():
    f, n, m = line.split(":", 2)
    m = m.strip().rstrip(".,;:").replace("/", "\\")
    if "\\" not in m:
        continue
    c = m.split("\\", 1)[1].rstrip("\\").lower()
    if "{" in c:  # brace list -> expand a{b,c} one level
        head, _, rest = c.partition("{")
        alts, _, tail = rest.partition("}")
        for a in alts.split(","):
            cites[head + a + tail].add(f"{f}:{n}")
    elif c:
        cites[c].add(f"{f}:{n}")
exact = {c: v for c, v in cites.items() if (BUILD / c).exists()}
prefix = {c: v for c, v in cites.items() if c not in exact}

per_cite = defaultdict(int)
rows = []
roots = defaultdict(lambda: defaultdict(int))
stack = [BUILD]
while stack:
    d = stack.pop()
    for e in os.scandir(d):
        st = e.stat(follow_symlinks=False)
        if st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            continue
        if e.is_dir(follow_symlinks=False):
            stack.append(Path(e.path))
            continue
        rel = str(Path(e.path).relative_to(BUILD)).lower()
        parts = rel.split("\\")
        hit = [a for a in ("\\".join(parts[:i]) for i in range(1, len(parts) + 1)) if a in exact]
        hit += [c for c in prefix if rel.startswith(c)]
        who = set().union(*(cites[c] for c in hit)) if hit else set()
        classes = {citer_class(w.split(":")[0]) for w in who}
        cov = next((k for k in ORDER if k in classes), "uncited")
        for c in hit:
            per_cite[c] += st.st_size
        top = parts[0] if len(parts) > 1 else "(loose)"
        roots[top][cov] += st.st_size
        roots[top]["total"] += st.st_size
        roots[top]["files"] += 1
        rows.append((rel, st.st_size, cov, ";".join(sorted(who))))

with open(HERE / "policy-files.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["path", "size", "coverage", "citers"]); w.writerows(rows)
with open(HERE / "policy-cited.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["cited", "exists", "bytes", "citers"])
    for c in sorted(cites):
        w.writerow([c, c in exact, per_cite[c], ";".join(sorted(cites[c]))])

M = 2**20
tot = defaultdict(int)
for d in roots.values():
    for k in ORDER:
        tot[k] += d[k]
print("total MiB by coverage: " + "  ".join(f"{k} {tot[k] / M:,.1f}" for k in ORDER))
print("root: total | " + " | ".join(ORDER))
for r, d in sorted(roots.items(), key=lambda x: -x[1]["total"]):
    print(f"  {r[:44]:44} {d['total'] / M:7.1f} {d['files']:6} | " + " ".join(f"{d[k] / M:6.1f}" for k in ORDER))
print("lasting/m1plan cited paths:")
for c in sorted(cites):
    cls = {citer_class(w.split(':')[0]) for w in cites[c]}
    if cls & {"lasting", "m1plan"}:
        print(f"  {per_cite[c] / M:7.1f} {'E' if c in exact else '-'} {c}  <- {','.join(sorted(cites[c]))[:110]}")
