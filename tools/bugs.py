"""Validated, full-record access to the canonical Markdown bug log."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys


DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "docs" / "BUGS.md"
ANCHOR = re.compile(r'<a id="bug-([0-9]{4,})"></a>')
HEADER = re.compile(
    r"- (SEVERE|MODERATE|MINOR) - ([^()]+?) "
    r"\((\d{4}-\d{2}-\d{2}[^()]*)\)\.\s+(.+)",
    re.DOTALL,
)


def parse_records(text: str) -> list[dict]:
    """Account for all owner-section text, failing on ambiguous record structure."""
    lines = text.splitlines()
    records: list[dict] = []
    identities: set[str] = set()
    owner = scope = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        number = index + 1
        if line.startswith("## "):
            owner, scope = line[3:].strip(), ""
            if not owner:
                raise ValueError(f"line {number}: empty owner")
            index += 1
            continue
        if line.startswith("### "):
            scope = line[4:].strip()
            index += 1
            continue
        anchor = ANCHOR.fullmatch(line)
        if anchor:
            identity = f"BUG-{anchor[1]}"
            if int(anchor[1]) < 1 or anchor[1] != f"{int(anchor[1]):04d}":
                raise ValueError(f"line {number}: noncanonical ID {identity}")
            if not owner or identity in identities:
                raise ValueError(f"line {number}: orphan or duplicate ID {identity}")
            identities.add(identity)
            index += 1
            while index < len(lines) and not lines[index].strip():
                index += 1
            start = index
            if index >= len(lines) or not lines[index].startswith("- "):
                raise ValueError(f"line {number}: {identity} has no entry")
            index += 1
            while index < len(lines) and lines[index].startswith("  "):
                if lines[index].lstrip().startswith(("- ", '<a id="bug-')):
                    raise ValueError(f"line {index + 1}: nested record or anchor")
                index += 1
            paragraph = "\n".join(lines[start:index])
            header = HEADER.fullmatch(paragraph)
            if not header:
                raise ValueError(f"line {start + 1}: malformed entry {identity}")
            severity, status, date_label, body = header.groups()
            if not status.strip():
                raise ValueError(f"line {start + 1}: empty status")
            date.fromisoformat(date_label[:10])
            category, separator, description = re.sub(r"\s+", " ", body).partition(". ")
            if not separator or not category.strip() or not description.strip():
                raise ValueError(f"line {start + 1}: missing category or description")
            records.append(dict(
                id=identity, owner=owner, scope=scope, severity=severity,
                status=status, date=date_label[:10], date_label=date_label,
                category=category, line_start=start + 1, line_end=index,
                anchor=f"bug-{anchor[1]}", text=paragraph,
            ))
            continue
        # Introductory conventions are outside owner sections. Within the log,
        # only headings, anchored paragraphs, blanks and dividers are admitted.
        if (owner and line.strip() and line != "---") or line.startswith(
            ("- SEVERE -", "- MODERATE -", "- MINOR -", '<a id="bug-')
        ):
            raise ValueError(f"line {number}: unaccounted text or missing ID")
        index += 1
    if not records:
        raise ValueError("no bug entries found")
    return records


def load_records(source: Path) -> tuple[list[dict], str]:
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    records = parse_records(raw.decode("utf-8-sig"))
    for record in records:
        record.update(source=str(source.resolve()), source_sha256=digest,
                      source_link=f"{source.resolve().as_posix()}#{record['anchor']}")
    return records, digest


def matches(record: dict, filters: argparse.Namespace) -> bool:
    for field in ("id", "owner", "scope", "category", "status", "severity"):
        values = getattr(filters, field)
        actual = record[field].casefold()
        if values and not any(
            value.casefold() in actual if field in ("owner", "scope", "category")
            else value.casefold() == actual for value in values
        ):
            return False
    search_text = " ".join(record["text"].casefold().split())
    return all(" ".join(term.casefold().split()) in search_text for term in filters.text)


def nonnegative(value: str) -> int:
    result = int(value)
    if result < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    for field in ("id", "owner", "scope", "category", "status", "severity", "text"):
        parser.add_argument(f"--{field}", action="append", default=[])
    parser.add_argument("--offset", type=nonnegative, default=0)
    parser.add_argument("--limit", type=nonnegative)
    parser.add_argument("--format", choices=("markdown", "jsonl"), default="markdown")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        records, digest = load_records(args.source)
        selected = [record for record in records if matches(record, args)]
        end = None if args.limit is None else args.offset + args.limit
        batch = selected[args.offset:end]
        if args.format == "jsonl":
            output = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in batch)
        else:
            output = "\n\n".join(
                f"### [{record['id']}](<{record['source_link']}>) — "
                f"{record['owner']} / {record['scope']}\n\n{record['text']}"
                for record in batch
            )
            if output:
                output += "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(output)
        else:
            sys.stdout.write(output)
        print(f"records={len(records)} matched={len(selected)} emitted={len(batch)} "
              f"offset={args.offset} source_sha256={digest}", file=sys.stderr)
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(2, f"bugs: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
