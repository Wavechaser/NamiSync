"""Export the app notices and pinned portable-runtime supplements offline."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def write_notices(source: Path, bundle: Path) -> None:
    """Write distribution notices from the selected source snapshot."""
    legal = (source / "namisync/interfaces/web/assets/legal_content.js").read_text(
        encoding="utf-8"
    )
    records = json.loads(legal.split("const notices = ", 1)[1].split("\n];", 1)[0] + "\n]")
    supplements = source / "tools/packaging/notices"
    for record in json.loads((supplements / "manifest.json").read_text(encoding="utf-8")):
        data = (supplements / record["file"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError(f"Notice identity mismatch: {record['file']}")
        records.append({**record, "text": data.decode("utf-8")})
    sections = [
        "NamiSync third-party notices\n"
        "===========================\n"
        "NamiSync is GPL-3.0-or-later; see LICENSE and BUILDING.txt.\n"
        "The following components retain their own terms. Python's complete\n"
        "installer/license corpus includes notices for optional components not\n"
        "collected here. Locked upstream package source and native components are\n"
        "unmodified. Embedded asset selections/adaptations are identified below.\n"
        "Microsoft binary conditions apply to Microsoft code, not NamiSync.\n"
        "Windows 11 supplies its system UCRT/API sets; those DLLs are not bundled.\n"
    ]
    for record in records:
        note = f"Note: {record['note']}\n" if record.get("note") else ""
        sections.append(
            f"\n{'=' * 72}\n{record['name']} — {record['version']}\n"
            f"Source: {record['source']}\n"
            f"Notice text SHA-256: {record['sha256']}\n{note}\n{record['text']}\n"
        )
    (bundle / "THIRD-PARTY-NOTICES.txt").write_text(
        "\n".join(sections), encoding="utf-8", newline="\n"
    )
