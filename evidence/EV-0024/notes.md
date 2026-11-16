Notes for "Release distribution census at b3095886 (2026-11-04)": text files chosen from `build/m1-release-20261104/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/m1-release-20261104/distribution/census.py`

````python
"""Inventory retained, verified local artifacts without rebuilding them."""
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parent
build = root.parent / "repeatable/build-d"
work = build / "work/namisync"
bundle = build / "dist/NamiSync"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def owner(source):
    if "site-packages" in source.parts:
        parts = source.parts[source.parts.index("site-packages") + 1:]
        return parts[0]
    if "pythoncore-3.13-64" in source.parts:
        return "CPython installation"
    if "codex-runtimes" in source.parts:
        return "ambient Codex runtime (provenance unresolved)"
    if source.is_relative_to(build):
        return "NamiSync/freezer output"
    if str(source) == "-":
        return "namespace package"
    return "UNACCOUNTED"


rows = []
for name, source, kind in ast.literal_eval((work / "COLLECT-00.toc").read_text(encoding="utf-8"))[0]:
    destination = bundle / (name if kind == "EXECUTABLE" else "_internal/" + name)
    source = Path(source)
    assert destination.is_file(), destination
    assert sha(destination) == sha(source), destination
    rows.append({"path": destination.relative_to(bundle).as_posix(), "kind": kind,
                 "source": str(source), "owner": owner(source), "sha256": sha(destination)})
for name in ("LICENSE", "START-HERE.txt"):
    rows.append({"path": name, "kind": "generated/copied guidance", "owner": "NamiSync",
                 "sha256": sha(bundle / name)})
assert {r["path"] for r in rows} == {p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file()}
assert not any(r["owner"] == "UNACCOUNTED" for r in rows)
identity = json.loads((build / "bundle-identity.json").read_text(encoding="utf-8"))
assert {"NamiSync/" + r["path"]: r["sha256"] for r in rows} == identity

modules = {}
for toc in ("Analysis-00.toc", "Analysis-01.toc"):
    for value in ast.literal_eval((work / toc).read_text(encoding="utf-8")):
        if not isinstance(value, list):
            continue
        for row in value:
            if not isinstance(row, tuple) or len(row) != 3 or row[2] not in ("PYMODULE", "PYSOURCE", "PYMODULE-1", "PYMODULE-2"):
                continue
            name, source, kind = row
            path = Path(source)
            modules[name, source] = {"name": name, "source": source, "owner": owner(path),
                                     "sha256": sha(path) if path.is_file() else None}
assert not any(r["owner"] == "UNACCOUNTED" for r in modules.values())
entrypoint_inputs = {}
for filename in ("PKG-00.toc", "PKG-01.toc", "EXE-00.toc", "EXE-01.toc"):
    for value in ast.literal_eval((work / filename).read_text(encoding="utf-8")):
        if not isinstance(value, list):
            continue
        for row in value:
            if not isinstance(row, tuple) or len(row) != 3:
                continue
            name, source, kind = row
            path = Path(source)
            if path.is_file():
                entrypoint_inputs[name, source] = {"name": name, "source": source,
                    "kind": kind, "owner": owner(path), "sha256": sha(path)}
legal = (build / "source/namisync/interfaces/web/assets/legal_content.js").read_text(encoding="utf-8")
notices = json.loads(legal.split("const notices = ", 1)[1].split("\n];", 1)[0] + "\n]")
result = {
    "purpose": "distribution preparation; not license clearance or candidate acceptance",
    "commit": json.loads((build / "source-identity.json").read_text())["commit"],
    "archive_sha256": sha(build / "NamiSync-windows-x64-dev.zip"),
    "bundle_files": rows,
    "bundle_owner_counts": dict(Counter(r["owner"] for r in rows)),
    "analysis_sources": list(modules.values()),
    "entrypoint_inputs": list(entrypoint_inputs.values()),
    "module_owner_counts": dict(Counter(r["owner"] for r in modules.values())),
    "existing_notices": [{k: n[k] for k in ("name", "version", "license", "source", "sha256")} for n in notices],
    "hosted_limit": "b3095886 downloaded bundle manifests were verified previously; hosted freezer origin tables were not uploaded",
}
(root / "census.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({"files": len(rows), "modules": len(modules), "owners": result["bundle_owner_counts"], "module_owners": result["module_owner_counts"]}, indent=2))
````
