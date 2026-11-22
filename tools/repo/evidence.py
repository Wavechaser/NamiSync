"""Stable IDs, manifest upkeep and validation for promoted records in tracked evidence/."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys


DEFAULT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = "manifest.json"
FILE_CAP = 256 << 10
RECORD_CAP = 1 << 20
FILE_LIMIT = 24
ID = re.compile(r"EV-([0-9]{4,})")
CITATION = re.compile(r"\bEV-[0-9]{4,}\b")
PATH_CITATION = re.compile(r"(?:(?<=[^\w/.-])|^)(?:\.{1,2}/)*evidence/(EV-[0-9]{4,})/([^\s`)>\]\"'<|*#?]*)")
RECORD_KEYS = ("id", "title", "date", "origin", "files")
FILE_KEYS = ("path", "bytes", "sha256")


def evidence_dir(root: Path) -> Path:
    return root / "evidence"


def render(manifest: dict) -> str:
    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"


def load(root: Path) -> tuple[dict, str]:
    """Parse and structurally validate the manifest; return it with its exact text."""
    text = (evidence_dir(root) / MANIFEST).read_bytes().decode("utf-8")
    data = json.loads(text)
    validate(data)
    return data, text


def validate(data: object) -> None:
    if not isinstance(data, dict) or list(data) != ["format", "next_id", "records"] or data["format"] != 1:
        raise ValueError("manifest must be {format: 1, next_id, records}")
    next_id = data["next_id"]
    if type(next_id) is not int or next_id < 1 or not isinstance(data["records"], list):
        raise ValueError("next_id must be a positive integer and records a list")
    numbers = []
    for record in data["records"]:
        if not isinstance(record, dict) or tuple(record) != RECORD_KEYS:
            raise ValueError(f"record keys must be {RECORD_KEYS}: {record!r:.80}")
        match = ID.fullmatch(record["id"]) if isinstance(record["id"], str) else None
        if not match or match[1] != f"{int(match[1]):04d}" or int(match[1]) < 1:
            raise ValueError(f"noncanonical ID {record['id']!r}")
        numbers.append(int(match[1]))
        for key in ("title", "origin"):
            value = record[key]
            if not isinstance(value, str) or not value.strip() or value != value.strip() or not value.isprintable():
                raise ValueError(f"{record['id']}: {key} must be one nonblank, trimmed, printable line")
        if not isinstance(record["date"], str):
            raise ValueError(f"{record['id']}: date must be YYYY-MM-DD")
        date.fromisoformat(record["date"])
        if not isinstance(record["files"], list):
            raise ValueError(f"{record['id']}: files must be a list")
        for entry in record["files"]:
            if not isinstance(entry, dict) or tuple(entry) != FILE_KEYS:
                raise ValueError(f"{record['id']}: file keys must be {FILE_KEYS}")
            if (not isinstance(entry["path"], str) or type(entry["bytes"]) is not int or entry["bytes"] < 0
                    or not isinstance(entry["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])):
                raise ValueError(f"{record['id']}: malformed file entry {entry!r:.80}")
        paths = [entry["path"] for entry in record["files"]]
        if paths != sorted(set(paths)):
            raise ValueError(f"{record['id']}: file paths must be unique and sorted")
    if numbers != sorted(set(numbers)):
        raise ValueError("record IDs must be unique and in ascending order")
    if numbers and next_id <= numbers[-1]:
        raise ValueError(f"next_id {next_id} would reuse an ID")


def scan(folder: Path) -> list[dict]:
    """Describe every file below one record folder, refusing links and caps."""
    if not folder.is_dir() or os.lstat(folder).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError(f"{folder.name}: missing folder or link")
    files, seen = [], set()
    for current, dirs, names in os.walk(folder):
        for name in dirs + names:
            path = Path(current) / name
            if os.lstat(path).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError(f"{folder.name}: link not allowed: {path.relative_to(folder).as_posix()}")
        for name in names:
            path = Path(current) / name
            relative = path.relative_to(folder).as_posix()
            if relative.casefold() in seen:
                raise ValueError(f"{folder.name}: case-colliding path {relative}")
            seen.add(relative.casefold())
            raw = path.read_bytes()
            if len(raw) > FILE_CAP:
                raise ValueError(f"{folder.name}: {relative} is {len(raw)} bytes; cap is {FILE_CAP}")
            files.append(dict(path=relative, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    files.sort(key=lambda entry: entry["path"])
    if not files:
        raise ValueError(f"{folder.name}: record has no files")
    if len(files) > FILE_LIMIT:
        raise ValueError(f"{folder.name}: {len(files)} files; limit is {FILE_LIMIT} (compact before promoting)")
    if sum(entry["bytes"] for entry in files) > RECORD_CAP:
        raise ValueError(f"{folder.name}: record exceeds {RECORD_CAP} bytes")
    return files


def citations(root: Path) -> list[tuple[str, int, str, str]]:
    """(file, line, ID, subpath) for each EV reference in root and docs/ Markdown."""
    found = []
    sources = sorted(root.glob("*.md")) + sorted(path for path in (root / "docs").rglob("*.md")
                                                  if "obsolete" not in path.relative_to(root / "docs").parts[:1])
    for source in sources:
        name = source.relative_to(root).as_posix()
        for number, line in enumerate(source.read_text(encoding="utf-8-sig").splitlines(), 1):
            paths = {(m[1], m[2].rstrip(".,;:!")) for m in PATH_CITATION.finditer(line.replace("\\", "/"))}
            for identity in sorted(set(CITATION.findall(line))):
                subpaths = sorted({sub for cited, sub in paths if cited == identity and sub}) or [""]
                found.extend((name, number, identity, sub) for sub in subpaths)
    return found


def check(root: Path) -> list[str]:
    problems = []
    manifest, text = load(root)
    if text != render(manifest):
        problems.append(f"{MANIFEST} is not in canonical form; run seal on an unchanged record to rewrite it")
    known = {record["id"]: record for record in manifest["records"]}
    for entry in sorted(evidence_dir(root).iterdir()):
        if entry.name != MANIFEST and entry.name not in known:
            problems.append(f"unmanifested entry evidence/{entry.name}")
    for identity, record in known.items():
        try:
            actual = scan(evidence_dir(root) / identity)
        except (OSError, ValueError) as error:
            problems.append(str(error))
            continue
        if actual != record["files"]:
            listed = {entry["path"]: entry for entry in record["files"]}
            present = {entry["path"]: entry for entry in actual}
            for path in sorted(listed.keys() | present.keys()):
                if listed.get(path) != present.get(path):
                    state = "missing" if path not in present else "unlisted" if path not in listed else "changed"
                    problems.append(f"{identity}: {state} {path}")
    for name, number, identity, sub in citations(root):
        record = known.get(identity)
        if record is None:
            problems.append(f"{name}:{number}: unknown {identity}")
        elif sub and not any(entry["path"] == sub or entry["path"].startswith(sub.rstrip("/") + "/")
                             for entry in record["files"]):
            problems.append(f"{name}:{number}: {identity} has no {sub}")
    return problems


def write(root: Path, manifest: dict) -> None:
    target = evidence_dir(root) / MANIFEST
    temporary = target.with_name(MANIFEST + ".tmp")
    temporary.write_bytes(render(manifest).encode("utf-8"))
    os.replace(temporary, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="allocate the next ID and an empty record folder")
    add.add_argument("--title", required=True)
    add.add_argument("--origin", required=True, help="where the files came from, e.g. build path and commit")
    add.add_argument("--date", default=date.today().isoformat())
    seal = commands.add_parser("seal", help="record a record folder's current files in the manifest")
    seal.add_argument("id")
    commands.add_parser("check", help="validate manifest, record files and EV citations")
    listing = commands.add_parser("list", help="print records with their citations")
    listing.add_argument("--format", choices=("markdown", "jsonl"), default="markdown")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "check":
            problems = check(root)
            for problem in problems:
                print(problem)
            records = load(root)[0]["records"]
            print(f"evidence: records={len(records)} problems={len(problems)}", file=sys.stderr)
            return 1 if problems else 0
        manifest, _ = load(root)
        if args.command == "add":
            identity = f"EV-{manifest['next_id']:04d}"
            record = dict(id=identity, title=args.title.strip(), date=args.date, origin=args.origin.strip(), files=[])
            manifest["records"].append(record)
            manifest["next_id"] += 1
            validate(manifest)
            try:
                (evidence_dir(root) / identity).mkdir()
            except FileExistsError:
                raise ValueError(f"evidence/{identity} already exists without a manifest entry; "
                                 "remove or restore it before adding") from None
            write(root, manifest)
            print(f"{identity} evidence/{identity}/")
        elif args.command == "seal":
            record = next((r for r in manifest["records"] if r["id"] == args.id), None)
            if record is None:
                raise ValueError(f"unknown record {args.id}")
            files = scan(evidence_dir(root) / args.id)
            present = {entry["path"]: entry for entry in files}
            altered = [entry["path"] for entry in record["files"] if present.get(entry["path"]) != entry]
            if altered:
                raise ValueError(f"{args.id}: sealed files changed or missing ({', '.join(altered)}); "
                                 "promoted files keep their bytes")
            record["files"] = files
            write(root, manifest)
            print(f"{args.id}: files={len(record['files'])} bytes={sum(f['bytes'] for f in record['files'])}")
        else:
            cited: dict[str, list[str]] = {}
            for name, number, identity, _ in citations(root):
                cited.setdefault(identity, []).append(f"{name}:{number}")
            for record in manifest["records"]:
                refs = sorted(set(cited.get(record["id"], [])))
                if args.format == "jsonl":
                    print(json.dumps(dict(record, cited_by=refs), ensure_ascii=False))
                else:
                    size = sum(entry["bytes"] for entry in record["files"])
                    print(f"{record['id']} — {record['title']} ({record['date']}; {len(record['files'])} files, "
                          f"{size} bytes); origin: {record['origin']}; cited by: {', '.join(refs) or 'none'}")
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(2, f"evidence: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
