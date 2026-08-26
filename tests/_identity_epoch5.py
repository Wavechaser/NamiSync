"""Read the immutable, pre-3R.14 capture; never regenerate expected old bytes."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path


_ARTIFACT = Path(__file__).with_name("assets") / "identity_epoch5_vectors.json"
_ARTIFACT_SHA256 = "52f80f8539b863da0a357ba4a47c20a32cb77a5a14db9194d5adf98e31c538d9"


def _frozen_bytes(section: str, name: str) -> bytes:
    raw = _ARTIFACT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == _ARTIFACT_SHA256
    entry = json.loads(raw)[section][name]
    data = base64.b64decode(entry["base64"], validate=True)
    assert len(data) == entry["byte_length"]
    assert hashlib.sha256(data).hexdigest() == entry["sha256"]
    return data


def frozen_vector(name: str) -> bytes:
    return _frozen_bytes("vectors", name)


def frozen_execution(with_identity: bool) -> bytes:
    return _frozen_bytes("execution_v6", "full128" if with_identity else "identityless")
